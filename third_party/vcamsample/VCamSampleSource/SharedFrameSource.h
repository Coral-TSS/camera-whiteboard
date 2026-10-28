// 本地新增：从共享帧文件读取白板画面（协议见 specs/windows11/frame-protocol.md）
#pragma once

#include <cstdint>
#include <string>

// 头部固定 64 字节，字段布局与 Python 生产者一致（小端）
#pragma pack(push, 1)
struct SharedFrameHeader
{
	uint32_t magic;			// 0x31425743 'CWB1'
	uint32_t version;		// 1
	uint32_t headerBytes;	// 64
	uint32_t width;
	uint32_t height;
	uint32_t stride;
	uint32_t format;		// 0 = BGRA8 预乘
	uint32_t reserved0;
	uint64_t seq;			// 序号锁：偶数稳定，奇数写入中
	uint64_t frameId;
	uint64_t timestamp;		// 100ns
	uint32_t state;			// 0 无帧 / 1 有效 / 2 故障占位
	uint32_t reserved2;
};
#pragma pack(pop)

static_assert(sizeof(SharedFrameHeader) == 64, "header must be 64 bytes");

class SharedFrameSource
{
public:
	SharedFrameSource() = default;
	~SharedFrameSource();

	SharedFrameSource(const SharedFrameSource&) = delete;
	SharedFrameSource& operator=(const SharedFrameSource&) = delete;

	// 把共享帧写入 sample 的缓冲区；不可用（文件缺失、尺寸不符、读到撕裂、格式不支持）时返回 false
	bool FillSample(IMFSample* sample, REFGUID format, UINT width, UINT height);

	// 最近 2 秒内是否读到过有效帧
	bool HasRecentFrame() const;

	void Close();

private:
	bool EnsureOpen();
	bool ReadHeader(SharedFrameHeader& header) const;
	static bool ResolveFilePath(std::wstring& path);

	HANDLE _file{};
	HANDLE _mapping{};
	const BYTE* _view{};
	ULONGLONG _lastValidTime{};	// MFGetSystemTime 口径，100ns
	ULONGLONG _lastFrameId{};
	ULONGLONG _lastFrameIdTime{};	// frameId 上次变化的时间，用于判断生产者是否已停
};
