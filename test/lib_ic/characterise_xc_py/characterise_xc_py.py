# Copyright 2018-2021 XMOS LIMITED.
# This Software is subject to the terms of the XMOS Public Licence: Version 1.
from __future__ import division
from __future__ import print_function
from builtins import str
from builtins import range
import sys
import os

package_dir = os.path.dirname(os.path.abspath(__file__))
path1 = os.path.join(package_dir,'../../../audio_test_tools/python/')
path2 = os.path.join(package_dir,'../../python/')

sys.path.append(path1)
sys.path.append(path2)

from audio_generation import get_band_limited_noise, write_data
import test_wav_ic
import subprocess
import time
import numpy as np
import scipy.io.wavfile as wavfile
import audio_wav_utils as awu
import argparse
import pyroomacoustics as pra
import scipy

NOISE_FLOOR_dBFS = -63.0
SIGMA2_AWGN = ((10 ** (float(NOISE_FLOOR_dBFS)/20)) * np.iinfo(np.int32).max) ** 2

PHASES = 6
FRAME_ADVANCE = 240
PROC_FRAME_LENGTH = 512

SAMPLE_RATE = 16000
SAMPLE_COUNT = 160080

MIN_NOISE_FREQ = 0

ROOM_X = 4.0
ROOM_Y = 4.0
ROOM_Z = 2.0

MIC_X_POINT = ROOM_X / 2 - 0.1
MIC_Y_POINT = ROOM_Y / 2 + 0.1
MIC_Z_POINT = ROOM_Z / 2

MIC_SPACING = 0.072
MIC_0_X = MIC_X_POINT - MIC_SPACING / 2
MIC_1_X = MIC_X_POINT + MIC_SPACING / 2

NOISE_DISTANCE = 1.5


IC_XE = os.path.join(package_dir, '../test_wav_ic/bin/test_wav_ic.xe')

# Use Sabine's Eq to calc average absorption factor of room surfaces
def get_absorption(x, y, z, rt60):
    V = x * y * z
    S = (2 * x * y) + (2 * x * z) + (2 * y * z)
    absorption = 0.1611 * V/(S * rt60)
    return absorption

def generate_test_audio(filename, audio_dir, max_freq, db, angle_theta, rt60, samples=SAMPLE_COUNT):
    file_path = os.path.join(audio_dir, filename)
    try:
        os.makedirs(audio_dir)
    except os.error as e:
        pass

    noise = get_band_limited_noise(MIN_NOISE_FREQ, max_freq, samples=samples, db=db, sample_rate=SAMPLE_RATE)
    audio_anechoic = np.asarray(noise * np.iinfo(np.int32).max, dtype=np.int32)

    noise_x = MIC_X_POINT + (NOISE_DISTANCE * np.cos(angle_theta))
    noise_y = MIC_Y_POINT + (NOISE_DISTANCE * np.sin(angle_theta))
    room_dim = [ROOM_X, ROOM_Y, ROOM_Z]

    if noise_x > ROOM_X or noise_x < 0 or noise_y > ROOM_Y or noise_y < 0:
        raise Exception("Speech location (%.2r, %.2r) outside room dimensions (%r, %r)"%(noise_x, noise_y, ROOM_X, ROOM_Y))

    absorption = get_absorption(ROOM_X, ROOM_Y, ROOM_Z, rt60)
    shoebox = pra.ShoeBox(room_dim, absorption=absorption, fs=SAMPLE_RATE, max_order=15, sigma2_awgn=SIGMA2_AWGN)
    shoebox.add_source([noise_x, noise_y, 1], signal=audio_anechoic)
    mics = np.array([[MIC_0_X, MIC_Y_POINT, 1], [MIC_1_X, MIC_Y_POINT, 1]]).T
    shoebox.add_microphone_array(pra.MicrophoneArray(mics, shoebox.fs))
    shoebox.simulate()

    mic_output = shoebox.mic_array.signals.T
    z = np.zeros((len(mic_output), 2), dtype=np.float64)
    combined = np.append(mic_output, z, axis=1)
    output = np.array(combined, dtype=np.int32)
    scipy.io.wavfile.write(file_path, SAMPLE_RATE, output)


def process_py(input_file, output_file, x_channel_delay, audio_dir="."):
    test_wav_ic.test(os.path.join(audio_dir, input_file),
                     os.path.join(audio_dir, output_file),
                     PHASES, FRAME_ADVANCE, PROC_FRAME_LENGTH, x_channel_delay)


def process_xc(input_file, output_file, audio_dir="."):
    cmd = ["axe", IC_XE]
    subprocess.check_output(["cp", input_file, "input.wav"], cwd=audio_dir)
    try:
        output = subprocess.check_output(cmd, cwd=audio_dir)
    except subprocess.CalledProcessError as e:
        msg = """Error! Running XC SUP failed.
               \ncmd: %
               \noutput: %s
               \nreturn_code: %d"""\
               % (str(e.cmd), e.output, e.returncode)
        raise Exception(msg)

    mv_cmd = ["mv", "output.wav", output_file]
    try:
        output = subprocess.check_output(mv_cmd, cwd=audio_dir)
    except subprocess.CalledProcessError as e:
        msg = """Error! Running XC SUP failed.
               \ncmd: %s
               \noutput: %s
               \nreturn_code: %d"""\
               % (str(e.cmd), e.output, e.returncode)
        raise Exception(msg)

    subprocess.check_output(["rm", "input.wav"], cwd=audio_dir)


def get_attenuation(input_file, output_file, audio_dir="."):
    in_rate, in_wav_file = wavfile.read(os.path.join(audio_dir, input_file))
    out_rate, out_wav_file = wavfile.read(os.path.join(audio_dir, output_file))

    in_wav_data, in_channel_count, in_file_length = awu.parse_audio(in_wav_file)
    out_wav_data, out_channel_count, out_file_length = awu.parse_audio(out_wav_file)

    # Calculate EWM of audio power in 1s window
    in_power_l = np.power(in_wav_data[0, :], 2)
    in_power_r = np.power(in_wav_data[1, :], 2)
    out_power = np.power(out_wav_data[0, :], 2)

    attenuation = []

    for i in range(len(in_power_l) // SAMPLE_RATE):
        window_start = i*SAMPLE_RATE
        window_end = window_start + SAMPLE_RATE
        av_in_power_l = np.mean(in_power_l[window_start:window_end])
        av_in_power_r = np.mean(in_power_r[window_start:window_end])
        av_in_power = (av_in_power_l + av_in_power_r) / 2

        av_out_power = np.mean(out_power[window_start:window_end])
        new_atten = 10 * np.log10(av_in_power / av_out_power) if av_out_power != 0 else 1000
        attenuation.append(new_atten)

    return attenuation

def get_attenuation_xc_py(test_id, noise_band, noise_db, angle_theta, rt60, x_channel_delay):
    input_file = "input_{}.wav".format(test_id) # Required by test_wav_suppression.xe
    output_file_py = "output_{}_py.wav".format(test_id)
    output_file_xc = "output_{}_xc.wav".format(test_id)

    audio_dir = test_id
    generate_test_audio(input_file, audio_dir, noise_band, noise_db, angle_theta, rt60)
    process_py(input_file, output_file_py, x_channel_delay, audio_dir)
    process_xc(input_file, output_file_xc, audio_dir)

    attenuation_py = get_attenuation(input_file, output_file_py, audio_dir)
    attenuation_xc = get_attenuation(input_file, output_file_xc, audio_dir)

    print("PYTHON SUP: {}".format(["%.2f"%item for item in attenuation_py]))
    print("    XC SUP: {}".format(["%.2f"%item for item in attenuation_xc]))

    return attenuation_xc, attenuation_py


def angle_type(x):
    x = int(x)
    if x > 180 or x < 0:
        raise argparse.ArgumentTypeError("%r not in range [0, 180]"%(x,))
    return x


def rt60_type(x):
    x = float(x)
    if x <= 0.0:
        raise argparse.ArgumentTypeError("%r not greater than 0"%(x,))
    return x


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--angle", nargs='?', default=90, type=angle_type, help="Angular position of noise source")
    parser.add_argument("--rt60", nargs='?', default=90, type=rt60_type, help="RT60 of environment")
    parser.add_argument("--noise_band", nargs='?', default=8000, type=int, help="Noise freq bandwidth")
    parser.add_argument("--noise_level", nargs='?',default=-20, type=int, help="Nominal noise level (dBFS)")
    parser.add_argument("--ic_delay", nargs='?',default=80, type=int, help="IC x channel delay")
    args = parser.parse_args()
    return args


def main():
    start_time = time.time()
    args = parse_arguments()
    angle_theta = args.angle * np.pi/180
    get_attenuation_xc_py("test", args.noise_band, args.noise_level, angle_theta, args.rt60, args.ic_delay)
    print("--- {0:.2f} seconds ---".format(time.time() - start_time))


if __name__ == "__main__":
    main()
