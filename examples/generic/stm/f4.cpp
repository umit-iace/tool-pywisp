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
    struct {
        DIO powergood {GPIO_PIN_9, GPIOB, GPIO_MODE_INPUT, GPIO_PULLUP};
        TIMER::HW tim {TIM5, 83, 1000}; // 84MHz/(83+1)/1000 == 1kHz
        TIMER::PWM fan{{
            .tim = &tim,
            .chan = TIM_CHANNEL_2,
            .pin = AFIO {GPIO_PIN_1, GPIOA, GPIO_AF2_TIM5},
        }};
    } supply;

    TIMER::HW pwmTim{TIM3, (2 - 1), 1500}; // APB1=84MHz/2 -> 42MHz; -> 42MHz/1500 = ~28kHz

    TIMER::PWM input = TIMER::PWM{{
             .tim = &pwmTim,
             .chan = TIM_CHANNEL_1,
             .pin = AFIO{GPIO_PIN_6, GPIOC, GPIO_AF2_TIM3,
                 GPIO_PULLDOWN
             },
     }};
} board{};

Support::Support()
    : min{.in{board.serialMin}, .out{board.serialMin}} {}

void Support::init() {
    board.supply.fan.pwm(0.8);
    k.every(1, [](uint32_t, uint32_t) {
    });
    e.during(e.RUN).every(500, [](uint32_t, uint32_t) {
            board.led.toggle();
    });
    e.during(e.IDLE).every(2000, [](uint32_t, uint32_t) {
            board.led.toggle();
    });
    e.onEvent(e.STOP).call([](uint32_t) {
            board.input.pwm(0);
    });
}

void Pendulum::reset() {
}

void Pendulum::setInput(double val) {
    board.input.pwm(fmin(1, fmax(0, val)));
}

void Pendulum::updateState(uint32_t t, uint32_t dt) {
}

Kernel k;
Support support;
Experiment e{&support.min.reg};

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

