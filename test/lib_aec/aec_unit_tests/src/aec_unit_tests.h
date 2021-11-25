// Copyright 2018-2021 XMOS LIMITED.
// This Software is subject to the terms of the XMOS Public Licence: Version 1.
#ifndef AEC_UNIT_TESTS_
#define AEC_UNIT_TESTS_

#include "unity.h"

#ifdef __XC__

#include <xs1.h>
#include <string.h>
#include <math.h>

#include <xclib.h>

#include "audio_test_tools.h"
extern "C" {
#include "aec_defines.h"
}
#include "aec_memory_pool.h"

#define TEST_ASM 1
#define MULTI_CORE 1

// Set F to a power of 2 greater than 1 to speedup testing by a Fx
#undef F
#if SPEEDUP_FACTOR
    #define F (SPEEDUP_FACTOR)
#else
    #define F 1
#endif

#endif // __XC__

#endif /* AEC_UNIT_TESTS_ */
