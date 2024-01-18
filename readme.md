190123 - DPC - V2.1

- Added support for a config.ini file
- Added enabled/disabled flag that cuts script out entirely if marked as disabled"
- Fixed some var issues when grabbing manifest
- Added trimmed list of files based on important file types, config variable to switch between behaviours.

280922 - DPC - v2.0

- Added testing functionality for liveliness.. 
- Tidied the manifest up so only a trimmed list is provided for the loop
- Added pid checking at script start

240922 - DPC - BlackVue grab script.

Written to reach out to my BlackVue dash cam, pull the files down and sort into folders.

Ongoing project. 

Need to add:

- Testing so the script breaks if the host isn't available
- Sorting of files into folders for front/rear cameras
- Verification that existing files on the filesystem aren't re-downloaded if they exist
