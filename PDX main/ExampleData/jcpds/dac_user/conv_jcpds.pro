pro conv_jcpds, filenames

nfiles = n_elements(filenames)

for i=0, nfiles-1 do begin
	; read version 3 files
	readat_jcpds3, filenames[i], dat
	;spawn, 'copy '+filename[i]+' '+filename[i]+'3'
	; output new format files
	spawn, 'delete '+filenames[i]
	wridat_jcpds4, filenames[i], dat
endfor

end

