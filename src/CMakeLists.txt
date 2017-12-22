cmake_minimum_required (VERSION 3.2)

# Skip compiler check.
set(CMAKE_SHARED_LIBRARY_LINK_C_FLAGS "")
set(CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS "")

# 'NONE' means no compiler check.
project (scd NONE)

add_custom_target(create_zip COMMAND
    ${CMAKE_COMMAND} -E tar "cfv" "${CMAKE_CURRENT_BINARY_DIR}/print_records.zip" --format=zip "print_records.py"
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

