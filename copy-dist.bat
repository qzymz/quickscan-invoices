@echo off
echo Copying frontend assets to Tauri dist...
mkdir src-tauri\dist\css 2>nul
mkdir src-tauri\dist\js 2>nul
copy /Y templates\index.html src-tauri\dist\index.html
copy /Y static\css\style.css src-tauri\dist\css\style.css
copy /Y static\js\app.js src-tauri\dist\js\app.js
echo Done.
