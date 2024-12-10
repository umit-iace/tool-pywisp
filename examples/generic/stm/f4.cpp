/** @file f4.cpp
 *
 * Copyright (c) 2024 IACE
 */
#include <core/experiment.h>
#include <sys/hal.h>
#include <sys/encoder.h>
#include <sys/pwm.h>
#include <sys/uart.h>

#include "model.h"
#include "support.h"

static void SystemClockReset();

static void SystemClockConfig();

struct board {
    bool initclocks = [](){
        SystemClockReset();
        SystemClockConfig();
        __HAL_RCC_GPIOA_CLK_ENABLE();
        __HAL_RCC_GPIOB_CLK_ENABLE();
        __HAL_RCC_GPIOC_CLK_ENABLE();

        __HAL_RCC_USART1_CLK_ENABLE();
        __HAL_RCC_TIM2_CLK_ENABLE();
        __HAL_RCC_TIM3_CLK_ENABLE();
        __HAL_RCC_TIM4_CLK_ENABLE();
        __HAL_RCC_TIM5_CLK_ENABLE();

        HAL_NVIC_EnableIRQ(USART1_IRQn);
        return true;
    }();
    DIO led {GPIO_PIN_8, GPIOB};
    DIO button {GPIO_PIN_0, GPIOA, GPIO_MODE_INPUT, GPIO_PULLUP};
    UART::HW serialMin{{
        .uart = USART1,
        .rx = AFIO {GPIO_PIN_10, GPIOA, GPIO_AF7_USART1},
        .tx = AFIO {GPIO_PIN_9, GPIOA, GPIO_AF7_USART1},
        .baudrate = 115200,
    }};
    TIMER::Encoder enc{{
        .tim = TIM4,
        .a = AFIO {GPIO_PIN_6, GPIOB, GPIO_AF2_TIM4},
        .b = AFIO {GPIO_PIN_7, GPIOB, GPIO_AF2_TIM4},
        .factor =  2 * M_PI / 8000,
        .filter = 0xf,
    }};
    Filter::MACD diff { 7, 30, 1 };
    struct {
        DIO powergood {GPIO_PIN_9, GPIOB, GPIO_MODE_INPUT, GPIO_PULLUP};
        TIMER::HW tim {TIM5, 83, 1000}; // 84MHz/(83+1)/1000 == 1kHz
        TIMER::PWM fan{{
            .tim = &tim,
            .chan = TIM_CHANNEL_2,
            .pin = AFIO {GPIO_PIN_1, GPIOA, GPIO_AF2_TIM5},
        }};
    } supply;

    struct {
        TIMER::HW tim {TIM2, 41, 1000}; // 84MHz/(41+1)/1000 == 2kHz
        MotorDriver driver {{
            .pwm = TIMER::PWM {{
                .tim = &tim,
                .chan = TIM_CHANNEL_4,
                .pin = AFIO {GPIO_PIN_3, GPIOA, GPIO_AF1_TIM2},
            }},
            .enA = DIO {GPIO_PIN_4, GPIOA},
            .enB = DIO {GPIO_PIN_5, GPIOA},
        }};
        TIMER::Encoder enc {{
            .tim = TIM3,
            .a = AFIO {GPIO_PIN_6, GPIOA, GPIO_AF2_TIM3},
            .b = AFIO {GPIO_PIN_7, GPIOA, GPIO_AF2_TIM3},
            .factor = -2 * M_PI / 2096 / 4,
            .filter = 0xf,
        }};
        Filter::MACD diff { 7, 30, 1 };
    } motor;
} board{};

void handleHWFrame(Frame &f) {
    auto enable = f.unpack<bool>();
    if (enable) {
        board.motor.driver.enable();
    } else {
        board.motor.driver.disable();
    }
}
void sendHWFrame(uint32_t t, uint32_t);

Support::Support()
    : min{.in{board.serialMin}, .out{board.serialMin}} {}

void Support::init() {
    board.supply.fan.pwm(0.8);
    k.every(1, [](uint32_t, uint32_t) {
            board.enc.measure();
            board.diff(board.enc.getPosition());
            board.motor.enc.measure();
            board.motor.diff(board.motor.enc.getPosition());
    });
    e.during(e.RUN).every(500, [](uint32_t, uint32_t) {
            board.led.toggle();
    });
    e.during(e.IDLE).every(2000, [](uint32_t, uint32_t) {
            board.led.toggle();
    });
    e.onEvent(e.STOP).call([](uint32_t) {
            board.motor.driver.disable();
    });
    min.reg.setHandler(5, handleHWFrame);
    e.during(e.RUN).every(20, sendHWFrame);
}

void Furuta::reset() {
    board.enc.zero();
    board.motor.enc.zero();
    board.diff.reset();
    board.motor.diff.reset();
}

void Furuta::setPwm(double val) {
    board.motor.driver.pwm(val);
}

void Furuta::updateState(uint32_t t, uint32_t dt) {
    state.th1(0) = board.motor.enc.getPosition();
    state.th1(1) = board.motor.diff();
    state.th2(0) = board.enc.getPosition();
    state.th2(1) = board.diff();
}

Kernel k;
Support support;
Experiment e{&support.min.reg};

void sendHWFrame(uint32_t t, uint32_t) {
    Frame f{7};
    f.pack(t).pack(!board.motor.driver.disabled);
    support.min.out.push(f);
}

int main() {
    k.every(1, support.min, &Min::poll);
    support.init();

    Model m;
    m.init();

    k.run();
}

extern "C" void USART1_IRQHandler() {
    board.serialMin.irqHandler();
}

static void SystemClockReset() {
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {
        .ClockType = RCC_CLOCKTYPE_SYSCLK
            | RCC_CLOCKTYPE_HCLK
            | RCC_CLOCKTYPE_PCLK1
            | RCC_CLOCKTYPE_PCLK2,
        .SYSCLKSource = RCC_SYSCLKSOURCE_HSI,
        .AHBCLKDivider = RCC_SYSCLK_DIV1,
        .APB1CLKDivider = RCC_HCLK_DIV1,
        .APB2CLKDivider = RCC_HCLK_DIV1,
    };

    while (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK);

    RCC_OscInitTypeDef RCC_OscInitStruct = {
        .OscillatorType = RCC_OSCILLATORTYPE_HSE
            | RCC_OSCILLATORTYPE_HSI
            | RCC_OSCILLATORTYPE_LSE
            | RCC_OSCILLATORTYPE_LSI,
        .HSEState = RCC_HSE_OFF,
        .LSEState = RCC_LSE_OFF,
        .HSIState = RCC_HSI_ON,
        .HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT,
        .LSIState = RCC_LSI_OFF,
        .PLL = {
            .PLLState = RCC_PLL_OFF,
        },
    };
    while (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK);
}

/**
 * @brief System clock configuration (84 MHz)
 */
static void SystemClockConfig() {
    /** Configure the main internal regulator output voltage */
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);
    /** Initializes the CPU, AHB and APB busses clocks */
    RCC_OscInitTypeDef RCC_OscInitStruct = {
        .OscillatorType = RCC_OSCILLATORTYPE_HSE,
        .HSEState = RCC_HSE_ON,
        .PLL = {
            .PLLState = RCC_PLL_ON,
            .PLLSource = RCC_PLLSOURCE_HSE,
            .PLLM = 25,
            .PLLN = 336,
            .PLLP = RCC_PLLP_DIV4, // => 84MHz
            .PLLQ = 7, // => 48MHz
        },
    };
    while (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK);
    /** Initializes the CPU, AHB and APB busses clocks */
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {
        .ClockType = RCC_CLOCKTYPE_SYSCLK
            | RCC_CLOCKTYPE_HCLK
            | RCC_CLOCKTYPE_PCLK1
            | RCC_CLOCKTYPE_PCLK2,
        .SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK,
        .AHBCLKDivider = RCC_SYSCLK_DIV1, // => 84MHz
        .APB1CLKDivider = RCC_HCLK_DIV2, // => 42MHz, TIM: 84MHz
        .APB2CLKDivider = RCC_HCLK_DIV2, // => 42MHz, TIM: 84MHz
    };

    while (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK);
}

