set(CMAKE_SYSTEM_NAME XCORE)
set(CMAKE_SYSTEM_VERSION 0.0.1)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/etc/xc/")

if(DEFINED XMOS_TOOL_PATH)
    set(CMAKE_C_COMPILER "${XMOS_TOOL_PATH}/xcc")
    set(CMAKE_XC_COMPILER "${XMOS_TOOL_PATH}/xcc")
    set(CMAKE_CXX_COMPILER  "${XMOS_TOOL_PATH}/xcc")
    set(CMAKE_ASM_COMPILER  "${XMOS_TOOL_PATH}/xcc")
    set(CMAKE_AR "${XMOS_TOOL_PATH}/xmosar" CACHE FILEPATH "Archiver")
    set(CMAKE_C_COMPILER_AR "${XMOS_TOOL_PATH}/xmosar")
    set(CMAKE_XC_COMPILER_AR "${XMOS_TOOL_PATH}/xmosar")
    set(CMAKE_CXX_COMPILER_AR "${XMOS_TOOL_PATH}/xmosar")
    set(CMAKE_ASM_COMPILER_AR "${XMOS_TOOL_PATH}/xmosar")
else()
    # message(WARNING "${COLOR_YELLOW}XMOS_TOOL_PATH not specified.  CMake will assume tools have been added to PATH.${COLOR_RESET}")
    set(CMAKE_C_COMPILER "xcc")
    set(CMAKE_XC_COMPILER  "xcc")
    set(CMAKE_CXX_COMPILER  "xcc")
    set(CMAKE_ASM_COMPILER  "xcc")
    set(CMAKE_AR "xmosar" CACHE FILEPATH "Archiver") # has to be cached in windows
    set(CMAKE_C_COMPILER_AR "xmosar")
    set(CMAKE_XC_COMPILER_AR "xmosar")
    set(CMAKE_CXX_COMPILER_AR "xmosar")
    set(CMAKE_ASM_COMPILER_AR "xmosar")
endif()

set(CMAKE_RANLIB "")
set(CMAKE_C_COMPILER_FORCED TRUE)
set(CMAKE_XC_COMPILER_FORCED TRUE)
set(CMAKE_CXX_COMPILER_FORCED TRUE)
set(CMAKE_ASM_COMPILER_FORCED TRUE)

set( XCORE ON CACHE BOOL "Building for xCore" )

if( NOT ( DEFINED XCORE_TARGET ) )
  set( XCORE_TARGET "XCORE-AI-EXPLORER" CACHE STRING "xCore hardware target" )
endif()

message(STATUS "XCORE_TARGET is ${XCORE_TARGET}" )

