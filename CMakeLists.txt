cmake_minimum_required(VERSION 3.25)

project(CameraWhiteboard
    VERSION 0.1.0
    DESCRIPTION "Desktop whiteboard feeding a Windows 11 virtual camera"
    LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

if(MSVC)
    add_compile_options(/W4 /permissive- /utf-8 /Zc:__cplusplus /EHsc)
    add_compile_definitions(UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
endif()

# 各原生组件自带 CMakeLists.txt；文件出现即自动纳入构建，未实现的组件不影响配置。
foreach(component manager media_source engine ipc)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/native/${component}/CMakeLists.txt")
        add_subdirectory("native/${component}")
    else()
        message(STATUS "跳过未实现的组件: native/${component}")
    endif()
endforeach()

if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests/native/CMakeLists.txt")
    enable_testing()
    add_subdirectory(tests/native)
endif()
