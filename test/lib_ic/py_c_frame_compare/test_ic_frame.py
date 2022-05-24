# Copyright 2022 XMOS LIMITED.
# This Software is subject to the terms of the XMOS Public Licence: Version 1.

import numpy as np
import scipy.io.wavfile
import audio_wav_utils as awu
import pytest
import sys, os

from build import ic_test_py
from ic_test_py import ffi
import ic_test_py.lib as ic_test_lib

package_dir = os.path.dirname(os.path.abspath(__file__))
pvc_path = os.path.join(package_dir, '../../shared/python')

sys.path.append(pvc_path)
try:
    import IC
except ModuleNotFoundError:
    print(f"Please install py_ic at root of project to support model testing")

import py_vs_c_utils as pvc 


proc_frame_length = 512
fd_length = proc_frame_length // 2 + 1
frame_advance = 240
num_phases = 10
y_channel_delay = 180
input_file = 'pytest_audio_0.wav'
#input_file = "../../../examples/bare-metal/ic/input.wav"
output_file = "output.wav"

@pytest.fixture(params=[34])
def pre_test_stuff(request):
    return request.param


class ic_comparison:
    def __init__(self):
        self.ic = IC.adaptive_interference_canceller(frame_advance, proc_frame_length, num_phases, 
        mu = 0.36956599983386695,
        delta = 7.450580593454381e-09, #two_mic_stereo.json
        K = 1,
        lamda = 0.9995117188,
        gamma = 2.0,
        leakage = 0.995,
        y_channel_delay = y_channel_delay,
        remove_NQ = False,
        vnr_model = '../../../../py_vnr/model_output_0_0_2/trained_model.h5',
        adaption_config = 'IC_ADAPTION_FORCE_ON'
        )
        ic_test_lib.test_init()

    def process_frame(self, frame):
        #we need to delay the y for python as not done in model
        #first copy the input data for C ver before we modfiy it
        frame_int = pvc.float_to_int32(frame)
        output_py, self.Error_ap = self.ic.process_frame(frame)
        mu, control_flag = self.ic.mu_control_system()
        #print('mu = ', mu, ', in_vnr = ', input_vnr_pred, ', out_vnr = ', output_vnr_pred, 'flag = ', control_flag)
        self.ic.adapt(self.Error_ap)

        #Grab a pointer to the data storage of the numpy arrays
        y_data = ffi.cast("int32_t *", ffi.from_buffer(frame_int[0].data))
        x_data = ffi.cast("int32_t *", ffi.from_buffer(frame_int[1].data))
        output_c = np.zeros((240), dtype=np.int32)
        output_c_ptr = ffi.cast("int32_t *", ffi.from_buffer(output_c.data))

        ic_test_lib.test_filter(y_data, x_data, output_c_ptr)

        vad = int(0)
        ic_test_lib.test_adapt(vad, output_c_ptr)

        #state = ic_test_lib.test_get_state()
        #print('mu_c = ', pvc.float_s32_to_float(state.mu[0][0]), ', nu_py = ', self.ic.mu)
        #print('leakage_c = ', pvc.float_s32_to_float(state.ic_adaption_controller_state.adaption_controller_config.leakage_alpha), ', leakage_py = ', self.ic.leakage)
        # print(pvc.float_s32_to_float(state.config_params.delta))
        return output_py, pvc.int32_to_float(output_c)

def check_filter_components(icc, frame_start):
    state = ic_test_lib.test_get_state()

    if frame_start < 1200:
        print('frame = ', frame_start // 240)
        print('Y:')
        exp = state.Y_bfp[0].exp
        for i in range(proc_frame_length + 2):
            c_Y = np.array(state.y[0][i]).astype(np.float64) * (2 ** exp)
            py_Y = 0
            if (i % 2) == 0:
                py_Y = icc.ic.Y_data[0][i // 2].real
            else:
                py_Y = icc.ic.Y_data[0][i // 2].imag
            rtol = np.ldexp(1, -13)
            if not np.isclose(c_Y, py_Y, rtol = rtol):
                print('C: ', c_Y, ', PY: ', py_Y)
                print('TEST FAILED at i = ', i)
            
        print('X_energy:')
        exp = state.X_energy_bfp[0].exp
        for i in range(fd_length):
            c_X_energy = np.array(state.X_energy[0][i]).astype(np.float64) * (2 ** exp)
            py_X_energy = icc.ic.X_energy[i]
            rtol = np.ldexp(1, -20)
            if not np.isclose(c_X_energy, py_X_energy, rtol = rtol):
                print('C: ', c_X_energy, ', PY: ', py_X_energy)
                print('TEST FAILED at i = ', i)
            
        print('Inverse X energy:')
        exp = state.inv_X_energy_bfp[0].exp
        print('exp = ', exp)
        for i in range(fd_length):
            c_inv_X_energy = np.array(state.inv_X_energy[0][i]).astype(np.float64) * (2 ** exp)
            py_inv_X_energy = icc.ic.inv_X_energy[0][i]
            rtol = np.ldexp(1, -10)
            if not np.isclose(c_inv_X_energy, py_inv_X_energy, rtol = rtol):
                print('C: ', c_inv_X_energy, ', PY: ', py_inv_X_energy)
                print('TEST FAILED at i = ', i)

        print('sigma_xx:')
        exp = state.sigma_XX_bfp[0].exp
        for i in range(fd_length):
            c_sigma_xx = np.array(state.sigma_XX[0][i]).astype(np.float64) * (2 ** exp)
            py_sigma_xx = icc.ic.sigma_xx[i]
            rtol = np.ldexp(1, -19)
            if not np.isclose(c_sigma_xx, py_sigma_xx, rtol = rtol):
                print('C: ', c_sigma_xx, ', PY: ', py_sigma_xx)
                print('TEST FAILED at i = ', i)

        if frame_start < 240:
            print('H_hat:')
            for ph in range(num_phases):
                exp = state.H_hat_bfp[0][ph].exp
                for i in range(proc_frame_length + 2):
                    c_H_hat = 0
                    py_H_hat = 0
                    if (i % 2) == 0:
                        c_H_hat = np.array(state.H_hat[0][ph][i // 2].re).astype(np.float64) * (2 ** exp)
                        py_H_hat = icc.ic.H[ph][i // 2].real
                    else:
                        c_H_hat = np.array(state.H_hat[0][ph][i // 2].im).astype(np.float64) * (2 ** exp)
                        py_H_hat = icc.ic.H[ph][i // 2].imag
                    rtol = np.ldexp(1, -12)
                    if not np.isclose(c_H_hat, py_H_hat, rtol = rtol):
                        print('C: ', c_H_hat, ', PY: ', py_H_hat)
                        print('TEST FAILED at ph = ', ph, ', i = ', i)

            print('Y_hat:')
            exp = state.Y_hat_bfp[0].exp
            for i in range(proc_frame_length + 2):
                c_Y_hat = 0
                py_Y_hat = 0
                if (i % 2) == 0:
                    c_Y_hat = np.array(state.Y_hat[0][i // 2].re).astype(np.float64) * (2 ** exp)
                    py_Y_hat = icc.ic.Y_hat[0][i // 2].real
                else:
                    c_Y_hat = np.array(state.Y_hat[0][i // 2].im).astype(np.float64) * (2 ** exp)
                    py_Y_hat = icc.ic.Y_hat[0][i // 2].imag
                rtol = np.ldexp(1, -15)
                if not np.isclose(c_Y_hat, py_Y_hat, rtol = rtol):
                    print('C: ', c_Y_hat, ', PY: ', py_Y_hat)
                    print('TEST FAILED at i = ', i)

            print('error_ap:')
            exp = state.error_bfp[0].exp
            for i in range(proc_frame_length + 2):
                c_error = np.array(state.Error[0][i]).astype(np.float64) * (2 ** exp)
                py_error = 0
                if (i % 2) == 0:
                    py_error = icc.Error_ap[0][i // 2].real
                else:
                    py_error = icc.Error_ap[0][i // 2].imag
                rtol = np.ldexp(1, -23)
                if not np.isclose(c_error, py_error, rtol = rtol):
                    print('C: ', c_error, ', PY: ', py_error)
                    print('TEST FAILED at i = ', i)

def test_frame_compare(pre_test_stuff):
    icc = ic_comparison()

    input_rate, input_wav_file = scipy.io.wavfile.read(input_file, 'r')
    input_wav_data, input_channel_count, file_length = awu.parse_audio(input_wav_file)
    delays = np.zeros(input_channel_count) #we do delay of y channel in process_frame above and in C rather than awu.get_frame

    output_wav_data = np.zeros((2, file_length))

    #for frame_start in range(0, file_length-proc_frame_length*2, frame_advance):
    for frame_start in range(0, 2400, frame_advance):
        input_frame = awu.get_frame(input_wav_data, frame_start, frame_advance, delays)[0:2,:]

        if False:
            print ('# ' + str(frame_start // frame_advance))

        output_py, output_c = icc.process_frame(input_frame)

        output_wav_data[0, frame_start: frame_start + frame_advance] = output_py
        output_wav_data[1, frame_start: frame_start + frame_advance] = output_c

        check_filter_components(icc, frame_start)

    #Write a copy of the output for post analysis if needed
    scipy.io.wavfile.write(output_file, input_rate, pvc.float_to_int32(output_wav_data.T))

    arith_closeness, geo_closeness, c_delay, peak2ave = pvc.pcm_closeness_metric(output_file)
    #assert arith_closeness > 0.98
    #assert geo_closeness > 0.99
    assert c_delay == 0
