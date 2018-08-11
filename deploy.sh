#!/usr/bin/env bash
set -e
echo 'Choose Operation:'
echo "1、package"
echo "2、package then install"
echo "3、package then upload"
echo "4、package then test"

read opnum

curWorkDir=$(cd "$(dirname "$0")"; pwd)
packageName="mppf"
distDir="/tmp/mppf_depoy_dist"
rm -rf $distDir
mkdir -p $distDir


doPackage(){
	rm -rf $distDir
	cd $curWorkDir
	python3 setup.py -q clean --all
	python3 setup.py -q bdist_wheel --dist-dir ${distDir}
	python3 setup.py -q clean --all

	archivePath=$distDir/$(ls $distDir)
	rm -rf "$(ls $curWorkDir | grep *.egg-info)"
	rm -rf "${curWorkDir}/build"
	echo $archivePath
}

if [[ $opnum =~ '1' ]]; then
	archivePath=$(doPackage)
	echo -e "\033[32m 打包完成: $archivePath \033[0m"
	open $distDir
fi

if [[ $opnum =~ '2' ]]; then
	archivePath=$(doPackage)
	echo -e "\033[32m 打包完成: $archivePath \033[0m"
	pip3 uninstall -y $packageName
	pip3 install $archivePath
fi

if [[ $opnum =~ '3' ]]; then
	archivePath=$(doPackage)
	echo -e "\033[32m 打包完成: $archivePath \033[0m"
	twine upload --config-file ~/.pypirc ${distDir}/*
fi

if [[ $opnum =~ '4' ]]; then
	virEnvDir="/tmp/testvirenv"
	archivePath=$(doPackage)
	echo -e "\033[32m 打包完成: $archivePath \033[0m"
	echo -e "\033[32m 新建虚拟环境: $virEnvDir \033[0m"
	rm -rf $virEnvDir
	mkdir -p $virEnvDir
	cd $virEnvDir
	virtualenv --no-site-packages venv
	source venv/bin/activate
	pip3 uninstall -y packageName
	pip3 install --upgrade "$archivePath"
	open $virEnvDir
	mppf
fi







