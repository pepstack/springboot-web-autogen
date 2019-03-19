#!/usr/bin/python
#-*- coding: UTF-8 -*-
#
# @file: sb2_webapp_gen.py
#
#   生成基于 java springboot2 的 webapp
#
# @version:
# @create: 2019-03-19
# @update: 2019-03-19
#
#######################################################################
import os, sys, stat, signal, shutil, inspect, commands, time, datetime

import yaml, codecs

import optparse, ConfigParser

#######################################################################
# application specific
APPFILE = os.path.realpath(sys.argv[0])
APPHOME = os.path.dirname(APPFILE)
APPNAME,_ = os.path.splitext(os.path.basename(APPFILE))
APPVER = "1.0.0"
APPHELP = "generate java springboot2 webapp"

#######################################################################
# import your local modules
import utils.utility as util
import utils.evntlog as elog

#######################################################################
def create_sb2_project(appConfig, options):
    sb2templateRoot = appConfig['sb2template']
    artifactRoot = options.artifactRootdir

    # 更改相应的设置
    groupPath = appConfig['pathSeparator'].join(options.groupId.split("."))
    artifactPath = os.path.join(groupPath, options.artifactName)

    # 目标路径
    artifactPrefix = os.path.join(artifactRoot, "src", "main", "java")
    artifactTestPrefix = os.path.join(artifactRoot, "src", "test", "java")
    artifactPathsConfig = {
        "pathPrefix": artifactPrefix,
        "groupPath": os.path.join(artifactPrefix, groupPath),
        "artifactPath": os.path.join(artifactPrefix, artifactPath),
        "configPath": os.path.join(artifactPrefix, artifactPath, "config"),
        "controllerPath": os.path.join(artifactPrefix, artifactPath, "controller"),
        "modelPath": os.path.join(artifactPrefix, artifactPath, "model"),
        "repositoryPath": os.path.join(artifactPrefix, artifactPath, "repository"),
        "servicePath": os.path.join(artifactPrefix, artifactPath, "service"),
        "serviceImplPath": os.path.join(artifactPrefix, artifactPath, "service", "impl"),
        "groupTestPath": os.path.join(artifactTestPrefix, groupPath),
        "artifactTestPath": os.path.join(artifactTestPrefix, artifactPath),
    }

    # 源路径
    templatePrefix = os.path.join(sb2templateRoot, "src", "main", "java")
    templateTestPrefix = os.path.join(sb2templateRoot, "src", "test", "java")
    templatePathsConfig = {
        "pathPrefix": templatePrefix,
        "groupPath": os.path.join(templatePrefix, "com", "pepstack"),
        "artifactPath": os.path.join(templatePrefix, "com", "pepstack", "webapp"),
        "configPath": os.path.join(templatePrefix, "com", "pepstack", "webapp", "config"),
        "controllerPath": os.path.join(templatePrefix, "com", "pepstack", "webapp", "controller"),
        "modelPath": os.path.join(templatePrefix, "com", "pepstack", "webapp", "model"),
        "repositoryPath": os.path.join(templatePrefix, "com", "pepstack", "webapp", "repository"),
        "servicePath": os.path.join(templatePrefix, "com", "pepstack", "webapp", "service"),
        "serviceImplPath": os.path.join(templatePrefix, "com", "pepstack", "webapp", "service", "impl"),
        "groupTestPath": os.path.join(templateTestPrefix, "com", "pepstack"),
        "artifactTestPath": os.path.join(templateTestPrefix, "com", "pepstack", "webapp"),
    }

    # 复制到目标位置
    util.copydirtree(sb2templateRoot, artifactRoot, (templatePathsConfig, artifactPathsConfig), options.verbose)

    # 替换文件内容
    replcmd = "%s --path='%s' --srcs='%%s' --dsts='%%s' --replace" % (os.path.join(APPHOME, "replace.py"), artifactRoot)
    
    cmdline = replcmd % ("com.pepstack", groupPath.replace(appConfig['pathSeparator'], '.'))
    os.system(cmdline)
    
    cmdline = replcmd % ("com.pepstack.webapp", artifactPath.replace(appConfig['pathSeparator'], '.'))
    os.system(cmdline)
    pass


#######################################################################
# main entry function
#
def main(parser, appConfig, loggerConfig):
    import utils.logger

    (options, args) = parser.parse_args(args=None, values=None)

    loggerDictConfig = utils.logger.set_logger(loggerConfig, options.log_path, options.log_level)

    elog.force("%s-%s start", APPNAME, APPVER)
    
    # 当前脚本绝对路径
    abspath = util.script_abspath(inspect.currentframe())

    options.artifactName = options.artifactName \
        .replace('${artifactId}', options.artifactId) \
        .replace('-', '_') \
        .replace('.', '_')

    options.artifactRootdir = options.artifactRootdir \
        .replace('${projectRootdir}', appConfig['projectRootdir']) \
        .replace('${artifactId}', options.artifactId) \
        .replace('${artifactName}', options.artifactName)

    if options.create_project:
        util.info2("projectRootdir = '%s'" % appConfig['projectRootdir'])
        util.info2("sb2template = '%s'" % appConfig['sb2template'])

        util.print_options_attrs(options, ['groupId', 'artifactId', 'artifactName', 'artifactVersion', 'artifactDescription', 'artifactRootdir'])

        if util.dir_exists(options.artifactRootdir) and not options.force:
            elog.warn("artifactRootdir has already existed. (using '--force' to overwrite it.)")
            sys.exit(-1)
            pass

        create_sb2_project(appConfig, options)

    elog.force("%s-%s exit.", APPNAME, APPVER)
    pass


#######################################################################
# Usage:
#    $ %prog
#  or
#    $ %prog --force
#
if __name__ == "__main__":
    parser, group, optparse = util.init_parser_group(
        appname = APPNAME,
        appver = APPVER,
        apphelp = APPHELP,
        usage = "%prog [Options]",
        group_options = os.path.join(APPHOME, "options/sb2_webapp_gen_options.yaml"))

    # 应用程序的缺省配置
    projectRootdir = os.path.dirname(APPHOME)

    appConfig = {
        "pathSeparator": os.path.sep,
        "projectRootdir": projectRootdir,
        "sb2template": os.path.join(projectRootdir, 'templates/springboot2'),
    }

    # 应用程序的日志配置
    logConfig = {
        'logging_config': os.path.join(APPHOME, 'config/logger.config'),
        'file': APPNAME + '.log',
        'name': 'main'
    }

    # 主函数
    main(parser, appConfig, logConfig)

    # 程序正常退出
    sys.exit(0)
