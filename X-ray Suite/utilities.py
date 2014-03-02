__author__ = 'Doomgoroth'


class Subscriptable(object):
    def __init__(self):
        self._subscriber = []

    def update_subscriber(self):
        for func in self._subscriber:
            func(self)

    def subscribe(self, func):
        self._subscriber.append(func)

    def unsubscribe(self, func):
        try:
            self._subscriber.remove(func)
        except:
            print func.toString() + ' is not currently subscribing'


class Spectrum(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Point(object):
    def __init__(self, _x, _y):
        self.x = _x
        self.y = _y


class FileIterator(object):
    def __init__(self, file_load_function):
        self.file_load_function = file_load_function

    def load_next_file(self, file_name):
        self.treat_file_string(file_name)
        new_file_name, new_file_name_with_leading_zeros = self._get_next_file_names()
        if os.path.isfile(new_file_name):
            self.file_load_function(new_file_name)
        elif os.path.isfile(new_file_name_with_leading_zeros):
            self.file_load_function(new_file_name_with_leading_zeros)

    def load_previous_file(self, file_name):
        self.treat_file_string(file_name)
        new_file_name, new_file_name_with_leading_zeros = self._get_previous_file_names()
        if os.path.isfile(new_file_name):
            self.file_load_function(new_file_name)
        elif os.path.isfile(new_file_name_with_leading_zeros):
            self.file_load_function(new_file_name_with_leading_zeros)

    def treat_file_string(self, file_name):
        self.file_name = file_name
        self._get_file_base_str()
        self._get_file_number()

    def _get_file_base_str(self):
        file_str = ''.join(self.file_name.split('.')[0:-1])
        self._file_base_str = '_'.join(file_str.split('_')[0:-1])
        self._file_ending = self.file_name.split('.')[-1]

    def _get_file_number(self):
        file_str = ''.join(self.file_name.split('.')[0:-1])
        num_str = file_str.split('_')[-1]
        try:
            self._file_number = int(num_str)
            self._num_char_amount = len(num_str)  #if number has leading zeros
        except ValueError:
            self._file_number = 0
            self._num_char_amount = 1

    def _get_next_file_names(self):
        new_file_name = self._file_base_str + '_' + str(self._file_number + 1) + \
                        '.' + self._file_ending
        format_str = '0' + str(self._num_char_amount) + 'd'
        number_str = ("{0:" + format_str + '}').format(self._file_number + 1)
        new_file_name_with_leading_zeros = self._file_base_str + '_' + \
                                           number_str + '.' + self._file_ending
        return new_file_name, new_file_name_with_leading_zeros

    def _get_previous_file_names(self):
        new_file_name = self._file_base_str + '_' + str(self._file_number - 1) + \
                        '.' + self._file_ending
        format_str = '0' + str(self._num_char_amount) + 'd'
        number_str = ("{0:" + format_str + '}').format(self._file_number - 1)
        new_file_name_with_leading_zeros = self._file_base_str + '_' + \
                                           number_str + '.' + self._file_ending
        return new_file_name, new_file_name_with_leading_zeros