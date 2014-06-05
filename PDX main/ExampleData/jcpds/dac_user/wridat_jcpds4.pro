pro wridat_jcpds4, datafile, dat
; write jcpds file with format version 4
; programmed by Sang-Heon Shim, 2000, Princeton University

; <examples>

; <notes>

; <arguments>

; <modification history>
; * feb 06 1999
;   - modify comments for howto

; <plan>
;-end howto-------------------------------

; error routine
on_ioerror, problem
!error=0

; output file check
filename=datafile
; check directory
cd, current=rootdir
;filename=filepath(root_dir=datadir,outfile)

openw, lun, /get, filename

; write version
printf, lun, 'VERSION: 4'

; write header
printf, lun, 'COMMENT: '+dat.header
; write symmetry_code, K0, K0p

printf, lun, 'K0: ', dat.k0
printf, lun, 'K0P: ', dat.k0p

case dat.s_code of
	1: sym = 'CUBIC'
	2: sym = 'HEXAGONAL'
	3: sym = 'TETRAGONAL'
	4: sym = 'ORTHORHOMBIC'
	5: sym = 'MONOCLINIC'
	6: sym = 'TRICLINIC'
endcase

printf, lun, 'SYMMETRY: '+sym

;* symmetry code change
;	ver 1.0	ver 2.0	ver 3.0
;1	cubic		cubic		cubic
;2	hexagonal	hexagonal	hexagonal
;3	-		orthorhombic	tetragonal
;4	-		tetragonal	orthorhombic
;5	-		monoclinic	monoclinic
;6	-				triclinic
case dat.s_code of
	1: begin
		printf, lun, 'A:', dat.cell[0]
	end
	2: begin
		printf, lun, 'A: ', dat.cell[0]
		printf, lun, 'C: ', dat.cell[2]
	end
	3: begin
		printf, lun, 'A: ', dat.cell[0]
		printf, lun, 'C: ', dat.cell[2]
	end
	4: begin
		printf, lun, 'A: ', dat.cell[0]
		printf, lun, 'B: ', dat.cell[1]
		printf, lun, 'C: ', dat.cell[2]
	end
	5: begin
		printf, lun, 'A: ', dat.cell[0]
		printf, lun, 'B: ', dat.cell[1]
		printf, lun, 'C: ', dat.cell[2]
		printf, lun, 'BETA: ', dat.cell[4]
	end
	6: begin
		printf, lun, 'A: ', dat.cell[0]
		printf, lun, 'B: ', dat.cell[1]
		printf, lun, 'C: ', dat.cell[2]
		printf, lun, 'ALPHA: ', dat.cell[3]
		printf, lun, 'BETA: ', dat.cell[4]
		printf, lun, 'GAMMA: ', dat.cell[5]
	end
endcase

volume = dat.cell[0]*dat.cell[1]*dat.cell[2]*$
	sqrt(1. - (cos(!dtor*dat.cell[3]))^2. - (cos(!dtor*dat.cell[4]))^2. - (cos(!dtor*dat.cell[5]))^2. $
	+ 2. * cos(!dtor*dat.cell[3])*cos(!dtor*dat.cell[4])*cos(!dtor*dat.cell[5]) )

;printf, lun, 'VOLUME: ', volume
printf, lun, 'ALPHAT: ', 0.0

get_size=size(dat.dsp)
numdata=get_size[1]
for i=0,numdata-1 do printf, lun, 'DIHKL: ', dat.dsp[i], dat.int[i], dat.h[i], dat.k[i], dat.l[i], format='(a7,f8.4,f8.0,3f8.2)'

; io error handling
problem:
if !error eq 1 then print, 'Error in input/output' else print, 'Write '+filename

free_lun, lun

end