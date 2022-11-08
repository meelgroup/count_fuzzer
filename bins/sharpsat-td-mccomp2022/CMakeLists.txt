cmake_minimum_required (VERSION 3.11 FATAL_ERROR)
project (SHARPSAT) 

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)
enable_language( CXX )

set(CMAKE_VERBOSE_MAKEFILE on)

if(POLICY CMP0092)
    # Disable passing /W3 by default on MSVC
    cmake_policy(SET CMP0092 NEW)
endif()

if(POLICY CMP0048)
    #policy for VERSION in cmake 3.0
    cmake_policy(SET CMP0048 NEW)
endif()


if(POLICY CMP0022)
    cmake_policy(SET CMP0022 NEW)
endif()

if(POLICY CMP0046)
    cmake_policy(SET CMP0046 NEW)
endif()

if(POLICY CMP0026)
    cmake_policy(SET CMP0026 NEW)
endif()

if(POLICY CMP0104)
    cmake_policy(SET CMP0104 NEW)
endif()


set(CMAKE_CXX_FLAGS "-std=c++11 -O3 -Wall -g")
SET(CMAKE_C_FLAGS "-std=c99 -Wall -msse4.1 -mpclmul")

option(STATIC "STATIC" OFF)
option(BUILD_SHARED_LIBS "shared" ON)
 
if(STATIC)
set(BUILD_SHARED_LIBS OFF)
endif(STATIC)

if ((${CMAKE_SYSTEM_NAME} MATCHES "Linux") OR (${CMAKE_SYSTEM_NAME} MATCHES "Darwin"))
    if(NOT BUILD_SHARED_LIBS)
        MESSAGE(STATUS "Compiling for static library use")
        if (${CMAKE_SYSTEM_NAME} MATCHES "Linux")
            set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static -Wl,--whole-archive -ldl -lpthread -Wl,--no-whole-archive -static ")
        endif()

        SET(CMAKE_FIND_LIBRARY_SUFFIXES ".a")

        # removing -rdynamic that's automatically added
        foreach (language CXX C)
            set(VAR_TO_MODIFY "CMAKE_SHARED_LIBRARY_LINK_${language}_FLAGS")
            string(REGEX REPLACE "(^| )-rdynamic($| )"
                                 " "
                                 replacement
                                 "${${VAR_TO_MODIFY}}")
            #message("Original (${VAR_TO_MODIFY}) is ${${VAR_TO_MODIFY}} replacement is ${replacement}")
            set(${VAR_TO_MODIFY} "${replacement}" CACHE STRING "Default flags for ${build_config} configuration" FORCE)
        endforeach()
    else()
        add_definitions(-DBOOST_TEST_DYN_LINK)
        MESSAGE(STATUS "Compiling for dynamic library use")
    endif()
endif()

if (STATICCOMPILE)
    set(Boost_USE_STATIC_LIBS ON)
endif()

find_library(GMP_LIB gmp)
find_library(GMPXX_LIB gmpxx)
find_library(MPFR_LIB mpfr)

add_definitions( -DMPFR_USE_NO_MACRO )
add_subdirectory(flowcutter)

SET(SOURCES 
	src/preprocessor/graph.cpp 
	src/preprocessor/instance.cpp
	src/preprocessor/oracle.cpp
	src/preprocessor/preprocessor.cpp
	src/preprocessor/subsumer.cpp
	src/preprocessor/treewidth.cpp
	src/preprocessor/twpp.cpp
	src/decomposition.cpp
	src/clhash/clhash.c
)

add_executable (sharpSAT src/main.cpp ${SOURCES})
target_link_libraries (sharpSAT ${MPFR_LIB} ${GMPXX_LIB} ${GMP_LIB})

add_executable (flow_cutter_pace17 flowcutter/pace.cpp)
target_link_libraries (flow_cutter_pace17 libflowcutter)
