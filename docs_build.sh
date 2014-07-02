#!/bin/bash
BUILD_NO=$1
BRANCH=$2

BUILD_SCRIPTS_HOME=docs_build_scripts.git
DOCS_HOME=docs_stage.git
DOCTOOLS_HOME=${DOCS_HOME}/doctools
IDL_HOME=docs_idl.git
DOCS_OUT=docs_out

/bin/rm -rf ${BUILD_SCRIPTS_HOME} ${DOCS_HOME} ${IDL_HOME} ${DOCS_OUT}
mkdir -p ${DOCS_OUT}

git clone git://git.xci-test.com/xenclient/build-scripts.git ${BUILD_SCRIPTS_HOME}

if [ x${BRANCH} != "xmaster" ];
then
(cd ${BUILD_SCRIPTS_HOME} && git checkout -b ${BRANCH} origin/${BRANCH} || exit 1 ) 
fi

git clone git://git.xci-test.com/xenclient/docs.git ${DOCS_HOME}

if [ x${BRANCH} != "xmaster" ];
then
(cd ${DOCS_HOME} && git checkout -b ${BRANCH} origin/${BRANCH} || exit 1 ) 
fi

${DOCS_HOME}/doctools/update_version_ents.sh ${BUILD_SCRIPTS_HOME}/version ${DOCS_HOME}/xml/en_us/docbook/shared/

XSL_PATH=${DOCS_HOME}/doctools/idl_to_docbook/

git clone git://git.xci-test.com/xenclient/idl.git ${IDL_HOME}
if [ x${BRANCH} != "xmaster" ];
then
(cd ${IDL_HOME} && git checkout -b ${BRANCH} origin/${BRANCH} || exit 1 ) 
fi

( cd ${IDL_HOME} && git checkout -b ${BRANCH} origin/${BRANCH} || exit 1)

${DOCS_HOME}/doctools/idl_to_docbook/update_idl_doc_ents.sh ${IDL_HOME}/interfaces/ ${DOCS_HOME}/xml/en_us/docbook/shared/ ${XSL_PATH}

#"ja" "fr" "it" "xh_hans" "es" "de"

for lang in "en_us" 
do
	echo [Building PDFs for language ${lang}]
	/bin/rm -rf ${DOCS_HOME}/${lang}
	mkdir -p ${DOCS_OUT}/${lang}
	
	(cd ${DOCS_OUT}/${lang} && rm -r *)
	
	for dir in "${DOCS_HOME}/xml/${lang}/docbook/public"
	do
		for d in $dir/*.xml; do
			if [ -f $d ]; then
				sed -i -e "s/<?dbtimestamp format=\"d B Y\"?>/<?dbtimestamp format=\"d B Y\"?> (build "$BUILD_NO")/" $d
			fi
		done

		(cd $dir && ./build.sh || exit 1) # && ./build_html_chunked.sh
	
		for pdf in $dir/out/pdf/*.pdf; do 
			if [ -f $pdf ]; then
				install -m 644 -c $pdf  ${DOCS_OUT}/${lang}
			fi
		done
	
		# tar cfC - $dir/out/html . | tar xvfC - ${DOCS_OUT}/${lang}
		
	
	done
done 
rm -rf ${BUILD_SCRIPTS_HOME} ${DOCS_HOME} ${IDL_HOME}
