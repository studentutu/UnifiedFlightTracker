cmake_minimum_required(VERSION 3.19)
project(vcqtdb LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Network)

qt_standard_project_setup()

add_executable(vcqtdb
    src/main.cpp
    src/MainWindow.cpp
    src/TrackerClient.cpp
    src/FlightModel.cpp
    src/PolarSkyView.cpp
    src/AltitudeStripChart.cpp
    src/KpiBar.cpp
)

target_include_directories(vcqtdb PRIVATE src)
target_link_libraries(vcqtdb PRIVATE
    Qt6::Core Qt6::Gui Qt6::Widgets Qt6::Network
)

# Warnings-as-friendly.
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(vcqtdb PRIVATE -Wall -Wextra -Wpedantic)
endif()
