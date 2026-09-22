cmake_minimum_required(VERSION 3.16)
project(fcitx5_voice VERSION 0.5.1 LANGUAGES CXX)

include(GNUInstallDirs)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(VOICEINPUT_SYSROOT "${CMAKE_CURRENT_SOURCE_DIR}/.tools/sysroot" CACHE PATH
    "Optional local sysroot containing Fcitx5 development files")
if(EXISTS "${VOICEINPUT_SYSROOT}/usr/include/Fcitx5/Core")
    find_library(FCITX5_CORE_LIBRARY NAMES libFcitx5Core.so.7
                 PATHS /usr/lib/${CMAKE_LIBRARY_ARCHITECTURE} REQUIRED
                 NO_DEFAULT_PATH)
    find_library(FCITX5_CONFIG_LIBRARY NAMES libFcitx5Config.so.6
                 PATHS /usr/lib/${CMAKE_LIBRARY_ARCHITECTURE} REQUIRED
                 NO_DEFAULT_PATH)
    find_library(FCITX5_UTILS_LIBRARY NAMES libFcitx5Utils.so.2
                 PATHS /usr/lib/${CMAKE_LIBRARY_ARCHITECTURE} REQUIRED
                 NO_DEFAULT_PATH)
    add_library(Fcitx5::Utils SHARED IMPORTED)
    set_target_properties(Fcitx5::Utils PROPERTIES
        IMPORTED_LOCATION "${FCITX5_UTILS_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${VOICEINPUT_SYSROOT}/usr/include/Fcitx5/Utils")
    add_library(Fcitx5::Config SHARED IMPORTED)
    set_target_properties(Fcitx5::Config PROPERTIES
        IMPORTED_LOCATION "${FCITX5_CONFIG_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${VOICEINPUT_SYSROOT}/usr/include/Fcitx5/Config"
        INTERFACE_LINK_LIBRARIES Fcitx5::Utils)
    add_library(Fcitx5::Core SHARED IMPORTED)
    set_target_properties(Fcitx5::Core PROPERTIES
        IMPORTED_LOCATION "${FCITX5_CORE_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${VOICEINPUT_SYSROOT}/usr/include/Fcitx5/Core"
        INTERFACE_LINK_LIBRARIES "Fcitx5::Config;Fcitx5::Utils")
    add_library(json-c::json-c STATIC IMPORTED)
    set_target_properties(json-c::json-c PROPERTIES
        IMPORTED_LOCATION "${VOICEINPUT_SYSROOT}/usr/lib/${CMAKE_LIBRARY_ARCHITECTURE}/libjson-c.a"
        INTERFACE_INCLUDE_DIRECTORIES "${VOICEINPUT_SYSROOT}/usr/include")
else()
    find_package(Fcitx5Core 5.1.19 CONFIG REQUIRED)
    find_package(json-c CONFIG REQUIRED)
endif()

add_library(voiceinput_core STATIC plugin/session.cpp)
set_target_properties(voiceinput_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(voiceinput_core PUBLIC plugin)
target_link_libraries(voiceinput_core PUBLIC json-c::json-c)
target_compile_options(voiceinput_core PRIVATE -Wall -Wextra -Wpedantic)

add_library(voiceinput MODULE plugin/voiceinput.cpp)
set_target_properties(voiceinput PROPERTIES PREFIX "" OUTPUT_NAME voiceinput)
target_compile_features(voiceinput PRIVATE cxx_std_20)
target_link_libraries(voiceinput PRIVATE voiceinput_core Fcitx5::Core)
target_compile_options(voiceinput PRIVATE -Wall -Wextra -Wpedantic)

set(VOICEINPUT_LIBRARY "${CMAKE_CURRENT_BINARY_DIR}/voiceinput")
configure_file(plugin/voiceinput.conf.in voiceinput.conf @ONLY)
set(VOICEINPUT_LIBRARY "voiceinput")
configure_file(plugin/voiceinput.conf.in voiceinput.install.conf @ONLY)

include(CTest)
if(BUILD_TESTING)
    add_executable(plugin_state_test tests/plugin_state_test.cpp)
    target_link_libraries(plugin_state_test PRIVATE voiceinput_core)
    add_test(NAME plugin_state COMMAND plugin_state_test)

    add_executable(plugin_buffer_test tests/plugin_buffer_test.cpp)
    target_include_directories(plugin_buffer_test PRIVATE plugin)
    add_test(NAME plugin_buffer COMMAND plugin_buffer_test)

    find_package(Threads REQUIRED)
    add_executable(plugin_integration_test tests/plugin_integration_test.cpp)
    target_compile_features(plugin_integration_test PRIVATE cxx_std_20)
    target_link_libraries(plugin_integration_test PRIVATE Fcitx5::Core json-c::json-c Threads::Threads)
    add_test(NAME plugin_integration COMMAND plugin_integration_test $<TARGET_FILE:voiceinput>)
    set_tests_properties(plugin_integration PROPERTIES TIMEOUT 15)

    add_executable(plugin_streaming_integration_test
                   tests/plugin_streaming_integration_test.cpp)
    target_compile_features(plugin_streaming_integration_test PRIVATE cxx_std_20)
    target_link_libraries(plugin_streaming_integration_test PRIVATE
                          Fcitx5::Core json-c::json-c Threads::Threads)
    add_test(NAME plugin_streaming_integration
             COMMAND plugin_streaming_integration_test $<TARGET_FILE:voiceinput>)
    set_tests_properties(plugin_streaming_integration PROPERTIES TIMEOUT 15)
    add_executable(plugin_hold_integration_test tests/plugin_hold_integration_test.cpp)
    target_compile_features(plugin_hold_integration_test PRIVATE cxx_std_20)
    target_link_libraries(plugin_hold_integration_test PRIVATE
                          Fcitx5::Core json-c::json-c Threads::Threads)
    add_test(NAME plugin_hold_integration
             COMMAND plugin_hold_integration_test $<TARGET_FILE:voiceinput>)
    set_tests_properties(plugin_hold_integration PROPERTIES TIMEOUT 15)

endif()

install(TARGETS voiceinput
        LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}/fcitx5")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/voiceinput.install.conf"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/fcitx5/addon"
        RENAME voiceinput.conf)
install(FILES LICENSE THIRD_PARTY_NOTICES.md MODEL_LICENSES.md
        DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/fcitx5-voice")
install(DIRECTORY licenses
        DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/fcitx5-voice")
install(FILES packaging/json-c-copyright
        DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/fcitx5-voice/packaging")
