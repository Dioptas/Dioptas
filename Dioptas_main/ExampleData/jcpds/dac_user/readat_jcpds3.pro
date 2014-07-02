;-------------------------------------------------------------
;+
; NAME:
;       READAT_JCPDS3
; PURPOSE:
;       Read jcpds version 3 file
; CATEGORY:
;				IO
; CALLING SEQUENCE:
;       readat_jcpds3, datafile, dat
; INPUTS:
;				datafile = data file name without extension or with full path+extension
; KEYWORD PARAMETERS:
; OUTPUTS:
;				dat = read data with structure
;							ver = version code
;							header = header
;							s_code = symmetry code
;							k0, k0p = elastic property (bulk modulus and pressure derivative of bulk modulus)
;							cell[6] = unit-cell parameters, i.e., a, b, c, alpha, beta, gamma
;							dsp = d-spacing
;							int = intensity
;							h, k, l = Miller index
; COMMON BLOCKS:
; EXAMPLES:
;				IDL> readat_jcpds3, "al2o3", dat
;				dat={ver:3, header:header1, s_code:sym, k0:k0, k0p:k0p, cell:[a,b,c,alpha,beta,gamma], $
;						dsp:dsp, int:int, h:h, k:k, l:l}
; NOTES:
;
; MODIFICATION HISTORY:
;       Written by Sang-Heon Shim, 1998.
;				Princetin University
;
; Copyright (C) 1999, Sang-Heon Shim
; This software may be used, copied, or redistributed as long as it is not
; sold and this copyright notice is reproduced on each copy made.  This
; routine is provided as is without any express or implied warranties
; whatsoever.
;-
;-------------------------------------------------------------
pro readat_jcpds3, datafile, dat

if n_params() ne 2 then begin
	message, 'Must have two parameters', /continue
	return
endif

; error handling
on_ioerror, problem

; check datafile
;filename=get_winpath(datafile,!dir_jcpds,'jcpds')

filename = datafile

file=findfile(filename,count=cnt)
if cnt eq 0 then begin
	print,'File "'+filename+'" not found.'
	return
endif

openr, lun, filename, /get_lun

; read version number
readf, lun, v
if v ne 3 then begin
	free_lun, lun
	print, 'Check version of your JCPDS format!'
	return
endif

; check header1
header1=' '
readf, lun, header1

; read symmetry, and K0, K0p
readf, lun, sym, k0, k0p

; read cell data
;* symmetry code change
;	ver 1.0	ver 2.0	ver 3.0
;1  cubic
;2	hexagonal
;3	tetragonal
;4	orthorhombic
;5	monoclinic
;6	triclinic
case sym of
	1: begin
		readf, lun, a
		b=a & c=a & alpha=90. & beta=90. & gamma=90.
	end
	2: begin
		readf, lun, a, c
		b=a & alpha=90. & beta=90. & gamma=120. &
	end
	3: begin
		readf, lun, a, c
		b=a & alpha=90. & beta=90. & gamma=90.
	end
	4: begin
		readf, lun, a, b, c
		alpha=90. & beta=90. & gamma=90.
	end
	5: begin
		readf, lun, a, b, c, beta
		alpha=90. & gamma=90.
	end
	6: readf, lun, a, b, c, alpha, beta, gamma
	else: begin
		free_lun, lun
		print, 'Illegal symmetry code'
		return
	end
endcase

; read 2 dummy lines
header2=' '
readf, lun, header2
readf, lun, header2

data=fltarr(5,1000)
; read data
i=0
temp=[0.0,0.0,0.0,0.0,0.0]
while (not eof(lun)) do begin
    readf, lun, temp
    data[*,i]=temp
    i=i+1
endwhile

free_lun, lun

numdata=i

; writing data
data = data(*,0:numdata-1)
dsp=fltarr(numdata) & int=fltarr(numdata)
h=fltarr(numdata) & k=fltarr(numdata) & l=fltarr(numdata)
dsp[*]=data[0,*] & int[*]=data[1,*]
h[*]=data[2,*] & k[*]=data[3,*] & l[*]=data[4,*]

; definition of variables
dat={ver:3, header:header1, s_code:sym, k0:k0, k0p:k0p, cell:[a,b,c,alpha,beta,gamma], $
	dsp:dsp, int:int, h:h, k:k, l:l}
return

problem:
if n_elements(lun) ne 0 then free_lun, lun
MESSAGE, !ERR_STRING, /NONAME, /IOERROR, /continue
return
end