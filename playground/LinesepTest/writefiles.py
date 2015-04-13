import os

file1 = open('without_linesep.txt', 'w')
file2 = open('with_linesep.txt', 'w')

for ind in xrange(20):
	file1.write('-----------\r\n')
	file2.write('-----------'+os.linesep)


file1.close()
file2.close()
