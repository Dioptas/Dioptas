;;  post install for windows

%PREFIX%\python.exe -m pip install --upgrade pip
%PREFIX%\Scripts\pip.exe install --upgrade fabio pyFAI

%PREFIX%\bin\dioptas makeshortcut
