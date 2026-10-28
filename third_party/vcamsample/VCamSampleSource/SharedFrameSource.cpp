// 本地新增：共享帧读取实现
#include "pch.h"
#include "Tools.h"
#include "WinTrace.h"
#include "SharedFrameSource.h"

// 由 dllmain.cpp 定义
extern HMODULE _hModule;

namespace
{
	constexpr uint32_t kMagic = 0x31425743;	// 'CWB1'
	constexpr uint32_t kHeaderBytes = 64;
	constexpr ULONGLONG kStaleTimeout = 2 * 10 * 1000 * 1000;	// 2 秒（100ns）

	std::wstring DirNameOf(const std::wstring& path)
	{
		auto pos = path.find_last_of(L"\\/");
		return pos == std::wstring::npos ? std::wstring() : path.substr(0, pos);
	}

	bool FileExists(const std::wstring& path)
	{
		auto attrs = GetFileAttributesW(path.c_str());
		return attrs != INVALID_FILE_ATTRIBUTES && !(attrs & FILE_ATTRIBUTE_DIRECTORY);
	}
}

SharedFrameSource::~SharedFrameSource()
{
	Close();
}

void SharedFrameSource::Close()
{
	if (_view)
	{
		UnmapViewOfFile(_view);
		_view = nullptr;
	}
	if (_mapping)
	{
		CloseHandle(_mapping);
		_mapping = nullptr;
	}
	if (_file && _file != INVALID_HANDLE_VALUE)
	{
		CloseHandle(_file);
	}
	_file = nullptr;
}

// 候选路径优先级：环境变量 > 与 DLL 同级的祖先目录下的 .run > ProgramData
bool SharedFrameSource::ResolveFilePath(std::wstring& path)
{
	wchar_t buffer[MAX_PATH];
	auto len = GetEnvironmentVariableW(L"CWB_FRAME_FILE", buffer, MAX_PATH);
	if (len > 0 && len < MAX_PATH)
	{
		path = buffer;
		if (FileExists(path))
			return true;
	}

	if (_hModule)
	{
		auto modulePath = wil::GetModuleFileNameW(_hModule);
		if (modulePath)
		{
			auto dir = DirNameOf(modulePath.get());
			// 从 DLL 所在目录逐级向上找 .run\frames.bin（开发期布局：<root>\third_party\vcamsample\x64\Release）
			for (int i = 0; i < 6 && !dir.empty(); i++)
			{
				auto candidate = dir + L"\\.run\\frames.bin";
				if (FileExists(candidate))
				{
					path = candidate;
					return true;
				}
				dir = DirNameOf(dir);
			}
		}
	}

	len = GetEnvironmentVariableW(L"ProgramData", buffer, MAX_PATH);
	if (len > 0 && len < MAX_PATH)
	{
		std::wstring candidate = std::wstring(buffer) + L"\\CameraWhiteboard\\frames.bin";
		if (FileExists(candidate))
		{
			path = candidate;
			return true;
		}
	}
	return false;
}

bool SharedFrameSource::EnsureOpen()
{
	if (_view)
		return true;

	std::wstring path;
	if (!ResolveFilePath(path))
		return false;

	HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
		nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
	if (file == INVALID_HANDLE_VALUE)
	{
		WINTRACE(L"SharedFrameSource: cannot open '%s' err:%u", path.c_str(), GetLastError());
		return false;
	}

	HANDLE mapping = CreateFileMappingW(file, nullptr, PAGE_READONLY, 0, 0, nullptr);
	if (!mapping)
	{
		WINTRACE(L"SharedFrameSource: CreateFileMapping failed err:%u", GetLastError());
		CloseHandle(file);
		return false;
	}

	auto view = static_cast<const BYTE*>(MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, 0));
	if (!view)
	{
		WINTRACE(L"SharedFrameSource: MapViewOfFile failed err:%u", GetLastError());
		CloseHandle(mapping);
		CloseHandle(file);
		return false;
	}

	_file = file;
	_mapping = mapping;
	_view = view;
	WINTRACE(L"SharedFrameSource: opened '%s'", path.c_str());
	return true;
}

bool SharedFrameSource::ReadHeader(SharedFrameHeader& header) const
{
	if (!_view)
		return false;

	// 序号锁：读前读后一致且为偶数，头部与像素才可信
	auto seq1 = *reinterpret_cast<const volatile uint64_t*>(_view + 32);
	if (seq1 == 0 || (seq1 & 1))
		return false;

	header = *reinterpret_cast<const SharedFrameHeader*>(_view);

	auto seq2 = *reinterpret_cast<const volatile uint64_t*>(_view + 32);
	if (seq1 != seq2)
		return false;

	if (header.magic != kMagic || header.version != 1 || header.headerBytes != kHeaderBytes)
		return false;
	if (header.width == 0 || header.height == 0 || header.stride < header.width * 4)
		return false;
	return true;
}

bool SharedFrameSource::FillSample(IMFSample* sample, REFGUID format, UINT width, UINT height)
{
	if (!sample)
		return false;

	SharedFrameHeader header{};
	if (!EnsureOpen() || !ReadHeader(header))
		return false;

	if (header.state != 1)
		return false;
	if (header.width != width || header.height != height)
	{
		// 尺寸不匹配时不做缩放，直接回落诊断图案
		return false;
	}

	// 生产者是否还在写：先看它自己写的时间戳（FILETIME），再看 frameId 是否停滞。
	// 只用本地计时不行——新建的媒体源实例第一次调用时没有历史，会把陈旧的最后一帧当成新帧。
	FILETIME ft{};
	GetSystemTimeAsFileTime(&ft);
	const ULONGLONG nowFileTime = ((ULONGLONG)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
	if (header.timestamp != 0 && nowFileTime > header.timestamp && (nowFileTime - header.timestamp) > kStaleTimeout)
	{
		return false;
	}

	const ULONGLONG now = MFGetSystemTime();
	if (header.frameId != _lastFrameId || _lastFrameIdTime == 0)
	{
		_lastFrameId = header.frameId;
		_lastFrameIdTime = now;
	}
	else if (now - _lastFrameIdTime > kStaleTimeout)
	{
		return false;
	}

	const BYTE* pixels = _view + kHeaderBytes;

	wil::com_ptr_nothrow<IMFMediaBuffer> buffer;
	if (FAILED(sample->GetBufferByIndex(0, &buffer)) || !buffer)
		return false;

	wil::com_ptr_nothrow<IMF2DBuffer2> buffer2D;
	if (FAILED(buffer->QueryInterface(IID_PPV_ARGS(&buffer2D))) || !buffer2D)
		return false;

	BYTE* scanline{};
	LONG pitch{};
	BYTE* start{};
	DWORD length{};
	if (FAILED(buffer2D->Lock2DSize(MF2DBuffer_LockFlags_Write, &scanline, &pitch, &start, &length)))
		return false;

	bool written = false;
	if (format == MFVideoFormat_RGB32)
	{
		const UINT rowBytes = width * 4;
		if (pitch >= (LONG)rowBytes)
		{
			for (UINT y = 0; y < height; y++)
			{
				CopyMemory(scanline + (size_t)y * pitch, pixels + (size_t)y * header.stride, rowBytes);
			}
			written = true;
		}
	}
	else if (format == MFVideoFormat_NV12)
	{
		const ULONG srcSize = (ULONG)header.stride * header.height;
		if (SUCCEEDED(RGB32ToNV12(const_cast<BYTE*>(pixels), srcSize, (LONG)header.stride,
			width, height, scanline, length, pitch)))
		{
			written = true;
		}
	}

	buffer2D->Unlock2D();

	if (written)
	{
		_lastValidTime = MFGetSystemTime();
		if (header.frameId != _lastFrameId)
		{
			_lastFrameId = header.frameId;
		}
	}
	return written;
}

bool SharedFrameSource::HasRecentFrame() const
{
	return _lastValidTime != 0 && (MFGetSystemTime() - _lastValidTime) < kStaleTimeout;
}
