import numpy as np
import data_processing.frame_preprocessor as fp
import py_vnr.vnr as vnr
import py_vnr.run_wav_vnr as rwv
import os
import test_utils
import matplotlib.pyplot as plt
import tensorflow as tf

def quantise_patch(model_file, this_patch):
    interpreter_tflite = tf.lite.Interpreter(model_path=model_file)
    # Get input and output tensors.
    input_details = interpreter_tflite.get_input_details()[0]
    output_details = interpreter_tflite.get_output_details()[0]
    # quantization spec
    if input_details["dtype"] in [np.int8, np.uint8]:
        input_scale, input_zero_point = input_details["quantization"]
        this_patch = this_patch / input_scale + input_zero_point
        this_patch = np.round(this_patch)
        this_patch = this_patch.astype(input_details["dtype"])
        return this_patch
    else:
        assert(False), "Need 8bit model for quantisation"
    if output_details["dtype"] in [np.int8, np.uint8]:
        output_scale, output_zero_point = output_details["quantization"]

tflite_model = os.path.abspath("../test_wav_vnr/model/model_output_0_0_2/model_qaware.tflite")
def test_vnr_extract_features(verbose=False):
    np.random.seed(1243)
    vnr_obj = vnr.Vnr(model_file=tflite_model) 

    input_data = np.empty(0, dtype=np.int32)
    input_words_per_frame = fp.FRAME_ADVANCE #No. of int32 values sent to dut as input per frame

    norm_patch_output_len = (fp.PATCH_WIDTH * fp.MEL_FILTERS)+1
    quant_patch_output_len = (fp.PATCH_WIDTH * fp.MEL_FILTERS)/4
    output_subsets_len = [norm_patch_output_len, quant_patch_output_len]
    output_words_per_frame =  norm_patch_output_len +  quant_patch_output_len #Both normalised and quantised patches sent as output

    input_data = np.append(input_data, np.array([input_words_per_frame, output_words_per_frame], dtype=np.int32))    
    min_int = -2**31
    max_int = 2**31
    test_frames = 1024
    ref_normalised_output = np.empty(0, dtype=np.float64)
    dut_normalised_output = np.empty(0, dtype=np.float64)

    x_data = np.zeros(fp.FRAME_LEN, dtype=np.float64)    
    for itt in range(0,test_frames):
        # Generate input data
        hr = np.random.randint(8)
        data = np.random.randint(min_int, high=max_int, size=fp.FRAME_ADVANCE)
        data = np.array(data, dtype=np.int32)
        data = data >> hr
        input_data = np.append(input_data, data)
        new_x_frame = data.astype(np.float64) * (2.0 ** -31) 

        # Ref form input frame implementation
        x_data = np.roll(x_data, -fp.FRAME_ADVANCE, axis = 0)
        x_data[fp.FRAME_LEN - fp.FRAME_ADVANCE:] = new_x_frame
        normalised_patch = rwv.extract_features(x_data, vnr_obj)
        ref_normalised_output = np.append(ref_normalised_output, normalised_patch)
        
    ref_quantised_output = quantise_patch(tflite_model, ref_normalised_output)
    op = test_utils.run_dut(input_data, "test_vnr_extract_features", os.path.abspath('../../../build/test/lib_vnr/vnr_unit_tests/bin/avona_test_vnr_extract_features.xe'))
    # Deinterleave dut output into normalised and quantised patches
    sections = []
    ii = 0
    count = 0
    while count < len(op):
        count = count + output_subsets_len[ii]
        sections.append(int(count))
        ii = (ii+1)%2
    
    op_split = np.split(op, sections)
    op_norm_patch = np.concatenate(([a for a in op_split[0::2]]))
    op_quant_patch = np.concatenate(([a for a in op_split[1::2]]))
    dut_quantised_output = op_quant_patch.view(np.int8)
    
    # Deinterleave normalised_patch exponent and mantissas
    exp_indices = np.arange(0, len(op_norm_patch), norm_patch_output_len) # One exponent for 96 mantissas block
    exp_indices = exp_indices.astype(np.int32)
    dut_exp = op_norm_patch[exp_indices]
    dut_mants = np.delete(op_norm_patch, exp_indices)
    assert len(dut_exp) == test_frames
    
    for fr in range(0,test_frames):
        # Compare normalised output
        dut = test_utils.int32_to_double(dut_mants[fr*(fp.PATCH_WIDTH * fp.MEL_FILTERS) : (fr+1)*(fp.PATCH_WIDTH * fp.MEL_FILTERS)], dut_exp[fr])
        ref = ref_normalised_output[fr*(fp.PATCH_WIDTH * fp.MEL_FILTERS) : (fr+1)*(fp.PATCH_WIDTH * fp.MEL_FILTERS)]
        dut_normalised_output = np.append(dut_normalised_output, dut)
        
        diff = np.abs((dut - ref))
        relative_diff = np.abs((dut - ref)/(ref+np.finfo(float).eps))
        assert(np.max(diff) < 0.005), f"ERROR: test_vnr_extract_features. frame {fr} normalised features max diff exceeds threshold" 
        assert(np.max(relative_diff) < 0.15), f"ERROR: test_vnr_extract_features. frame {fr} normalised features max relative diff exceeds threshold" 
        if verbose:
            ii = np.where(relative_diff > 0.05) 
            if len(ii[0]):
                for index in ii[0]:
                    print(f"frame {fr}. diff = {diff[index]}, ref {ref[index]} dut {dut[index]}")
        
        arith_closeness, geo_closeness = test_utils.get_closeness_metric(ref, dut)
        assert(geo_closeness > 0.999), f"ERROR: frame {fr}. normalised_output geo_closeness below pass threshold"
        assert(arith_closeness > 0.999), f"ERROR: frame {fr}. normalised_output arith_closeness below pass threshold"

        # Compare quantised output
        dut = dut_quantised_output[fr*(fp.PATCH_WIDTH * fp.MEL_FILTERS) : (fr+1)*(fp.PATCH_WIDTH * fp.MEL_FILTERS)]
        ref = ref_quantised_output[fr*(fp.PATCH_WIDTH * fp.MEL_FILTERS) : (fr+1)*(fp.PATCH_WIDTH * fp.MEL_FILTERS)]
        diff = np.abs((dut - ref))
        assert(np.max(diff) < 2)
    
    diff = np.abs((dut_normalised_output - ref_normalised_output))
    percent_diff = np.abs((dut_normalised_output - ref_normalised_output)/(ref_normalised_output+np.finfo(float).eps))
    
    print(f"max diff normalised patch = {np.max(diff)}")
    print(f"max diff percent normalised patch = {np.max(percent_diff)*100}%")

    print(f"max diff quantised output = {np.max(np.abs(dut_quantised_output - ref_quantised_output))}")

    plt.plot(ref_normalised_output)
    plt.plot(dut_normalised_output)
    #plt.show()

if __name__ == "__main__":
    test_vnr_extract_features()
