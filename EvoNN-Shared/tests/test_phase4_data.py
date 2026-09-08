"""Additive catalog coverage and protected raw-position text splits."""
import numpy as np
from evonn_shared.active_catalog import get_benchmark,load_parity_pack
from evonn_shared.catalog import list_benchmarks
from evonn_shared.datasets import _text_split
from evonn_shared.runtime_catalog import runtime_manifest


def test_extension_preserves_core_and_binds_real_sources():
    assert len(list_benchmarks())==8
    pack=load_parity_pack('tier_b_core_v2')
    assert {'banknote_classification','digits_image','shakespeare_byte_lm'}<=set(pack.benchmarks)
    for name in ('banknote_classification','shakespeare_byte_lm'):
        _,runtime=runtime_manifest(name)
        assert runtime['benchmarks'][name]['source_url'].startswith('https://')
        assert get_benchmark(name).status.value=='experimental'


def test_text_windows_never_cross_raw_partition_or_touch_test():
    _,runtime=runtime_manifest('shakespeare_byte_lm')
    binding=runtime['benchmarks']['shakespeare_byte_lm']
    tokens=np.arange(10000,dtype=np.int64)
    for seed in (0,42,43):
        arrays=_text_split(tokens,binding,seed)
        assert arrays['x_train'].max()<7000 and arrays['y_train'].max()<7000
        assert arrays['x_validation'].min()>=7000 and arrays['y_validation'].max()<8500
        np.testing.assert_array_equal(arrays['x_train'][:,-1]+1,arrays['y_train'])
        np.testing.assert_array_equal(arrays['x_validation'][:,-1]+1,arrays['y_validation'])
        assert len(arrays['x_train'])<=binding['train_limit']
