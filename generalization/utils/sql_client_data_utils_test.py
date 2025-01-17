# Copyright 2021, Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for sql_client_data_utils."""

import collections
import os

import numpy as np
import tensorflow as tf

from generalization.utils import sql_client_data_utils


class SqlClientDataUtilsTest(tf.test.TestCase):

  def test_serializer_parser_on_a_single_elem(self):
    elem = collections.OrderedDict(
        int8_scalar=tf.convert_to_tensor(0, dtype=tf.int8),
        int32_scalar=tf.convert_to_tensor(1, dtype=tf.int32),
        int64_scalar=tf.convert_to_tensor(2, dtype=tf.int64),
        int64_1darray=tf.convert_to_tensor([3, 4, 5], dtype=tf.int64),
        int64_2darray=tf.convert_to_tensor(np.eye(3), dtype=tf.int64),
        int64_3darray=tf.convert_to_tensor(np.ones((2, 3, 4)), dtype=tf.int64),
        float32_scalar=tf.convert_to_tensor(1.0, dtype=tf.float32),
        float32_1darray=tf.convert_to_tensor([3.0, 4.0, 5.0], dtype=tf.float32),
        float32_2darray=tf.convert_to_tensor(
            np.random.randn(3, 4), dtype=tf.float32),
        float32_3darray=tf.convert_to_tensor(
            np.random.randn(3, 4, 5), dtype=tf.float32),
        string=tf.convert_to_tensor('19260817', dtype=tf.string),
    )

    elem_spec = collections.OrderedDict([(key,
                                          tf.TensorSpec.from_tensor(tensor))
                                         for key, tensor in elem.items()])

    serializer = sql_client_data_utils.build_serializer(elem_spec)
    parser = sql_client_data_utils.build_parser(elem_spec)

    rebuilt_elem = parser(serializer(elem))

    self.assertEqual(elem.keys(), rebuilt_elem.keys())

    for key in rebuilt_elem.keys():
      self.assertAllEqual(elem[key], rebuilt_elem[key])

  def test_save_to_sql_client_data(self):
    test_ds1 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(
            i=[1, 2, 3], f=[4.0, 5.0, 6.0], s=['a', 'b', 'c']))
    test_ds2 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(i=[4, 5], f=[7.0, 8.0], s=['d', 'e']))
    test_client_dataset_mapping = {'foo': test_ds1, 'bar': test_ds2}
    test_client_ids = list(test_client_dataset_mapping.keys())

    dataset_fn = lambda cid: test_client_dataset_mapping[cid]

    database_filepath = os.path.join(self.get_temp_dir(), 'db')

    sql_client_data_utils.save_to_sql_client_data(test_client_ids, dataset_fn,
                                                  database_filepath)

    self.assertTrue(tf.io.gfile.exists(database_filepath))

    rebuilt_cd = sql_client_data_utils.load_parsed_sql_client_data(
        database_filepath, test_ds1.element_spec)

    self.assertCountEqual(rebuilt_cd.client_ids, test_client_ids)

    for cid in rebuilt_cd.client_ids:
      rebuilt_ds = rebuilt_cd.create_tf_dataset_for_client(cid)
      ds = test_client_dataset_mapping[cid]

      for rebuilt_odict, original_odict in zip(rebuilt_ds, ds):
        self.assertEqual(
            list(rebuilt_odict.keys()), list(original_odict.keys()))

        for key in rebuilt_odict.keys():
          self.assertAllEqual(rebuilt_odict[key], original_odict[key])

  def test_client_metadata(self):
    test_ds1 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(
            i=[1, 2, 3], f=[4.0, 5.0, 6.0], s=['a', 'b', 'c']))
    test_ds2 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(i=[4, 5], f=[7.0, 8.0], s=['d', 'e']))
    test_client_dataset_mapping = {'foo': test_ds1, 'bar': test_ds2}
    test_client_ids = list(test_client_dataset_mapping.keys())

    dataset_fn = lambda cid: test_client_dataset_mapping[cid]

    database_filepath = os.path.join(self.get_temp_dir(), 'db')

    sql_client_data_utils.save_to_sql_client_data(test_client_ids, dataset_fn,
                                                  database_filepath)

    self.assertTrue(tf.io.gfile.exists(database_filepath))

    df = sql_client_data_utils.load_sql_client_data_metadata(database_filepath)

    self.assertLen(df, len(test_client_ids))

    self.assertEqual(df.loc[df['client_id'] == 'foo'].num_examples.values, 3)
    self.assertEqual(df.loc[df['client_id'] == 'bar'].num_examples.values, 2)

  def test_save_to_sql_client_can_overwrite_if_enabled(self):
    test_ds1 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(
            i=[1, 2, 3], f=[4.0, 5.0, 6.0], s=['a', 'b', 'c']))
    test_ds2 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(i=[4, 5], f=[7.0, 8.0], s=['d', 'e']))
    test_client_dataset_mapping = {'foo': test_ds1, 'bar': test_ds2}
    test_client_ids = list(test_client_dataset_mapping.keys())

    dataset_fn = lambda cid: test_client_dataset_mapping[cid]

    database_filepath = os.path.join(self.get_temp_dir(), 'db')

    sql_client_data_utils.save_to_sql_client_data(test_client_ids[0:1],
                                                  dataset_fn, database_filepath)

    self.assertTrue(tf.io.gfile.exists(database_filepath))

    sql_client_data_utils.save_to_sql_client_data(
        test_client_ids, dataset_fn, database_filepath, allow_overwrite=True)

    self.assertTrue(tf.io.gfile.exists(database_filepath))

    rebuilt_cd = sql_client_data_utils.load_parsed_sql_client_data(
        database_filepath, test_ds1.element_spec)

    self.assertCountEqual(rebuilt_cd.client_ids, test_client_ids)

    for cid in rebuilt_cd.client_ids:
      rebuilt_ds = rebuilt_cd.create_tf_dataset_for_client(cid)
      ds = test_client_dataset_mapping[cid]

      for rebuilt_odict, original_odict in zip(rebuilt_ds, ds):
        self.assertEqual(
            list(rebuilt_odict.keys()), list(original_odict.keys()))

        for key in rebuilt_odict.keys():
          self.assertAllEqual(rebuilt_odict[key], original_odict[key])

  def test_save_to_sql_client_will_not_overwrite_if_not_allowed(self):

    test_ds1 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(
            i=[1, 2, 3], f=[4.0, 5.0, 6.0], s=['a', 'b', 'c']))
    test_ds2 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(i=[4, 5], f=[7.0, 8.0], s=['d', 'e']))
    test_client_dataset_mapping = {'foo': test_ds1, 'bar': test_ds2}
    test_client_ids = list(test_client_dataset_mapping.keys())

    dataset_fn = lambda cid: test_client_dataset_mapping[cid]

    database_filepath = os.path.join(self.get_temp_dir(), 'db')

    sql_client_data_utils.save_to_sql_client_data(test_client_ids[0:1],
                                                  dataset_fn, database_filepath)

    self.assertTrue(tf.io.gfile.exists(database_filepath))

    with self.assertRaises(FileExistsError):
      sql_client_data_utils.save_to_sql_client_data(
          test_client_ids, dataset_fn, database_filepath, allow_overwrite=False)

  def test_save_to_sql_client_data_raises_type_error(self):
    test_ds1 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(
            i=[1, 2, 3], f=[4.0, 5.0, 6.0], s=['a', 'b', 'c']))
    test_ds2 = tf.data.Dataset.from_tensor_slices(
        collections.OrderedDict(i=[7.0, 8.0], f=[4, 5], s=['d', 'e']))
    # Uses a different element_spec intentionally.

    test_client_dataset_mapping = {'foo': test_ds1, 'bar': test_ds2}
    test_client_ids = list(test_client_dataset_mapping.keys())

    dataset_fn = lambda cid: test_client_dataset_mapping[cid]

    database_filepath = os.path.join(self.get_temp_dir(), 'db')

    with self.assertRaises(TypeError):
      sql_client_data_utils.save_to_sql_client_data(test_client_ids, dataset_fn,
                                                    database_filepath)


if __name__ == '__main__':
  tf.test.main()
