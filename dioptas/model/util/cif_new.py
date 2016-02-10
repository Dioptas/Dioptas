# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


class CifPhase(object):
    """
    Phase created from a cif dictionary (a cif file can have several phases which can be read as a list by PyCifRw)

    This automatically creates symmetry equivalent position of atoms for further processing of the file.
    """

    def __init__(self, cif_dictionary):
        """

        :param cif_dictionary:
        :return:
        """
        self.cif_dictionary = cif_dictionary

        self.a = convert_cif_number_to_float(cif_dictionary['_cell_length_a'])
        self.b = convert_cif_number_to_float(cif_dictionary['_cell_length_b'])
        self.c = convert_cif_number_to_float(cif_dictionary['_cell_length_c'])

        self.alpha = convert_cif_number_to_float(cif_dictionary['_cell_angle_alpha'])
        self.beta = convert_cif_number_to_float(cif_dictionary['_cell_angle_beta'])
        self.gamma = convert_cif_number_to_float(cif_dictionary['_cell_angle_gamma'])

        self.volume = convert_cif_number_to_float(cif_dictionary['_cell_volume'])

        self.space_group = cif_dictionary['_symmetry_space_group_name_H-M']
        self.space_group_number = int(cif_dictionary['_symmetry_Int_Tables_number'])
        self.symmetry = self.get_symmetry_from_space_group_number(self.space_group_number)

        self.comments = ''
        self.read_file_information()

        if '_symmetry_equiv_pos_as_xyz' in cif_dictionary.keys():
            self.symmetry_operations = cif_dictionary['_symmetry_equiv_pos_as_xyz']
        elif '_space_group_symop_operation_xyz' in cif_dictionary.keys():
            self.symmetry_operations = cif_dictionary['_symmetry_equiv_pos_as_xyz']

        for i in range(len(self.symmetry_operations)):
            self.symmetry_operations[i] = self.symmetry_operations[i].replace("/", "./")

        self._atom_labels = cif_dictionary['_atom_site_label']
        self._atom_x = [float(s) for s in cif_dictionary['_atom_site_fract_x']]
        self._atom_y = [float(s) for s in cif_dictionary['_atom_site_fract_y']]
        self._atom_z = [float(s) for s in cif_dictionary['_atom_site_fract_z']]
        if '_atom_site_occupancy' in cif_dictionary.keys():
            self._atom_occupancy = [float(s) for s in cif_dictionary['_atom_site_occupancy']]
        else:
            self._atom_occupancy = [1] * len(self._atom_labels)

        # Create a list of 4-tuples, where each tuple is an atom:
        # [ ('Si', 0.4697, 0.0, 0.0),  ('O', 0.4135, 0.2669, 0.1191),  ... ]
        self.atoms = [(self._atom_labels[i], self._atom_x[i], self._atom_y[i], self._atom_z[i],
                       self._atom_occupancy[i]) for i in range(len(self._atom_labels))]
        self.clean_atoms()
        self.generate_symmetry_equivalents()

    def clean_atoms(self):
        """
        Cleaning all atom labels and check atom positions
        """
        for i in range(len(self.atoms)):
            (name, xn, yn, zn, occu) = self.atoms[i]
            xn = (xn + 10.0) % 1.0
            yn = (yn + 10.0) % 1.0
            zn = (zn + 10.0) % 1.0
            name = self.convert_element(name)
            self.atoms[i] = (name, xn, yn, zn, occu)

    def generate_symmetry_equivalents(self):
        # The CIF file consists of a few atom positions plus several "symmetry
        # operations" that indicate the other atom positions within the unit cell.  So
        # using these operations, create copies of the atoms until no new copies can be
        # made.

        # Two atoms are on top of each other if they are less than "eps" away.
        eps = 0.0001  # in Angstrom

        # For each atom, apply each symmetry operation to create a new atom.
        i = 0
        while (i < len(self.atoms)):

            label, x, y, z, occu = self.atoms[i]

            for op in self.symmetry_operations:

                # Python is awesome: calling e.g. eval('x,y,1./2+z') will convert the
                # string into a 3-tuple using the current values for x,y,z!
                xn, yn, zn = eval(op)

                # Make sure that the new atom lies within the unit cell.
                xn = (xn + 10.0) % 1.0
                yn = (yn + 10.0) % 1.0
                zn = (zn + 10.0) % 1.0

                # Check if the new position is actually new, or the same as a previous
                # atom.
                new_atom = True
                for at in self.atoms:
                    if (abs(at[1] - xn) < eps and abs(at[2] - yn) < eps and abs(at[3] - zn) < eps) \
                            and at[0] == label:
                        new_atom = False

                # If the atom is new, add it to the list!
                if (new_atom):
                    self.atoms.append((label, xn, yn, zn, occu))  # add a 4-tuple

            # Update the loop iterator.
            i += 1

        # Sort the atoms according to type alphabetically.
        self.atoms = sorted(self.atoms, key=lambda at: at[0])
        self.atoms.reverse()

    def convert_element(self, label):
        """
        Convert atom labels such as 'Oa1' into 'O'.
        """

        elem2 = ['He', 'Li', 'Be', 'Ne', 'Na', 'Mg', 'Al', 'Si', 'Cl', 'Ar', 'Ca', 'Sc', 'Ti',
                 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
                 'Rb', 'Sr', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
                 'Sb', 'Te', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd',
                 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu', 'Hf', 'Ta', 'Re', 'Os', 'Ir', 'Pt',
                 'Au', 'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th', 'Pa',
                 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr']

        if (label[0:2] in elem2):
            return label[0:2]

        elem1 = ['H', 'B', 'C', 'N', 'O', 'F', 'P', 'S', 'K', 'V', 'Y', 'I', 'W', 'U']

        if (label[0] in elem1):
            return label[0]

        print('WARNING: could not convert "%s" into element name!' % label)
        return label

    def get_symmetry_from_space_group_number(self, number):
        if number_between(number, 1, 2):
            return "TRICLINIC"
        if number_between(number, 3, 15):
            return "MONOCLINIC"
        if number_between(number, 16, 74):
            return "ORTHORHOMBIC"
        if number_between(number, 75, 142):
            return "TETRAGONAL"
        if number_between(number, 143, 167):
            return "TRIGONAL"
        if number_between(number, 168, 194):
            return "HEXAGONAL"
        if number_between(number, 195, 230):
            if self.alpha == 90 and self.beta == 90 and self.gamma == 90:
                return "CUBIC"
            else:
                return "RHOMBOHEDRAL"
        return None

    def read_file_information(self):
        """
        Reads in all the header information and tries to build a good description of the phase.
        """
        if self.cif_dictionary.get('_chemical_formula_structural'):
            self.comments += self.cif_dictionary['_chemical_formula_structural'].replace(" ", "")
            self.comments += ' - '
        elif self.cif_dictionary.get('_chemical_formula_analytical'):
            self.comments += self.cif_dictionary['_chemical_formula_analytical'].replace(" ", "")
            self.comments += ' - '

        if self.cif_dictionary.get('_chemical_name_structure_type'):
            self.comments += self.cif_dictionary['_chemical_name_structure_type']
            self.comments += ' structure type'
        if self.cif_dictionary.get('_database_code_icsd'):
            self.comments = self.comments.strip()
            if self.comments is not '':
                self.comments += ', ICSD '
            else:
                self.comments *= 'ICSD '
            self.comments += self.cif_dictionary['_database_code_icsd']


def number_between(num, num_low, num_high):
    """
    Tests if a number is in between num_low and num_high, whereby num_low and num_high are included  [num_low, num_high]
    :return: Boolean result for the result
    """
    if num >= num_low and num <= num_high:
        return True
    return False

def convert_cif_number_to_float(cif_number):
    return float(cif_number.split('(')[0])
