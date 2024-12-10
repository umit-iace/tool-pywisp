## config
stm32_fetch_cmsis(F4)
stm32_fetch_hal(F4)

find_package(CMSIS COMPONENTS STM32F401RC REQUIRED)
find_package(HAL COMPONENTS STM32F401RC REQUIRED)

add_executable(stm ${PROJECT_SOURCES} f4.cpp)

target_compile_options(stm PUBLIC
    # -fanalyzer
    -Wall
    # -Wextra
)

target_compile_features(stm PRIVATE cxx_std_17)

target_include_directories(stm PUBLIC .
	../inc
)

target_link_options(stm PUBLIC
	LINKER:--print-memory-usage
)

target_link_libraries(stm
	CMSIS::STM32::F401RC
	HAL::STM32::F4::CORTEX
	HAL::STM32::F4::DMA
	HAL::STM32::F4::GPIO
	HAL::STM32::F4::PWREx
	HAL::STM32::F4::RCCEx
	HAL::STM32::F4::TIMEx
	HAL::STM32::F4::UART
	STM32::NoSys
	tool-libs-stm-uart
	Eigen3::Eigen
)

add_custom_target(upload
	openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c "program stm.elf verify reset exit"
	DEPENDS stm
)
add_custom_target(upload_ota
    COMMAND arm-none-eabi-objcopy -O binary stm.elf stm.bin
    COMMAND echo uploading with curl to $(UPLOAD)
    COMMAND curl -v -F "update=@stm.bin" $(UPLOAD)/updateSTM
    DEPENDS stm
    BYPRODUCTS stm.bin
    VERBATIM
)
