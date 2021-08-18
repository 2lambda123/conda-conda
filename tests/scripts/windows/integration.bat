@ECHO ON
pushd %TEMP%
cd %GITHUB_WORKSPACE%
CALL dev-init.bat
CALL conda-build tests\test-recipes\activate_deactivate_package
CALL pytest -m "integration and not installed" --basetemp=C:\tmp -v --splits=%GROUP_COUNT% --group=%TEST_GROUP%
