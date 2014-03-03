import unittest
from XRS_Data import XRS_ImageData


class Test_DataTest(unittest.TestCase):
    def testFileIterator(self):
        data = XRS_ImageData()
        data.load_image_file('test_001.tif')
        data.load_next_image_file()
        self.assertEqual(data.file_name, 'test_002.tif')
        data.load_next_image_file()
        data.load_next_image_file()
        data.load_previous_image_file()
        self.assertEqual(data.file_name, 'test_003.tif')

    def testSubscriberPattern(self):
        data = XRS_ImageData()
        self.output_str = ''

        def test_function1(data_obj):
            self.output_str += 'running'

        def test_function2(data_obj):
            self.output_str += ' to'

        def test_function3(data_obj):
            self.output_str += ' hell!'

        data.subscribe(test_function1)
        data.subscribe(test_function2)
        data.subscribe(test_function3)
        data.update_subscriber()
        self.assertEqual(self.output_str, 'running to hell!')


if __name__ == '__main__':
    unittest.main()
