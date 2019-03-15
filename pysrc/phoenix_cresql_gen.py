#!/usr/bin/python
#-*- coding: UTF-8 -*-
#
# @file: phoenix_cresql_gen.py
#
#   生成 hbase phoenix 数据库创建语句文件
#
# @version: 2019-03-15 15:45:56
# @create: 2019-03-13
# @update: 2019-03-15 15:45:56
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
APPHELP = "generate phoenix cresql files"

#######################################################################
# import your local modules
import utils.utility as util
import utils.evntlog as elog

#######################################################################
# 对于Phoenix来说，HBase的rowkey会被转换成primary key，column family 如果不指定则为 '0'
#

# https://phoenix.apache.org/language/datatypes.html
field_type_cast = {
    "int": "INTEGER",
    "bigint": "BIGINT",
    "ub4": "INTEGER",
    "ub4hex": "INTEGER",
    "ub8": "BIGINT",
    "ub8hex": "BIGINT",
    "string": "VARCHAR",
    "str": "VARCHAR"
}

# 注释的最大长度
field_remarks_maxlen = 127

# 不要更改这个默认的 sequence 最大值 !
sequence_max_value=9223372036854775807

# 每次缓存的数目(默认100)
sequence_cache_number=100

# 每次缓存的数目
sequence_is_cycle=True

# SALT_BUCKETS=[ 1, 256]
salt_buckets_default = 20

###########################################################
# 查询表的主键:
#   SELECT column_name FROM system.catalog WHERE table_schem='sydb' AND table_name='connect' AND key_seq IS NOT NULL;
#
# 查询表的字段的注释 (remarks)
#   SELECT table_schem, table_name, column_family, column_name, remarks FROM system.catalog WHERE table_schem='sydb' AND table_name='connect';
#
#   !desc "sydb"."connect"
#
# 为表的字段增加注释 (remarks)
###########################################################
def comment_table_sql (table_schem, table_name, column_name, is_pk, comments, maxlen):
    sql = None

    if comments:
        u16lines = []

        for utf16line in comments:
            ustr = utf16line.strip("; ,.\n").replace('`', '').replace('"', '').replace("'", "")
            if len(ustr):
                u16lines.append(ustr)

        utf16str = ";".join(u16lines)[:maxlen]
        if len(utf16str) > 0:
            utf8line = utf16str.encode('utf-8')

            if column_name is None:
                # comment on table
                sql = '''UPSERT INTO SYSTEM.CATALOG(COLUMN_FAMILY,COLUMN_NAME,TABLE_NAME,TABLE_SCHEM,TENANT_ID,REMARKS) VALUES(NULL, NULL, '%s', '%s', NULL, '%s');''' % (table_name, table_schem, utf8line)
            else:
                if is_pk:
                    # comment on primary key column: column_family IS NULL
                    sql = '''UPSERT INTO SYSTEM.CATALOG(COLUMN_FAMILY,COLUMN_NAME,TABLE_NAME,TABLE_SCHEM,TENANT_ID,REMARKS) VALUES(NULL, '%s', '%s', '%s', NULL, '%s');''' % (column_name, table_name, table_schem, utf8line)
                else:
                    # comment on non-pk column: column_family = '0'
                    sql = '''UPSERT INTO SYSTEM.CATALOG(COLUMN_FAMILY,COLUMN_NAME,TABLE_NAME,TABLE_SCHEM,TENANT_ID,REMARKS) VALUES('0', '%s', '%s', '%s', NULL, '%s');''' % (column_name, table_name, table_schem, utf8line)

    return sql


def parse_table_comment (fields, comment):
    tblcomments = comment.split('\n')
    fldcomments = {}

    for fld in fields:
        for i in range(0, len(tblcomments)):
            line = tblcomments[i].strip()

            cols = []

            items = line.split(" - ")
            for item in items:
                cols.append(item.strip())

            if len(cols) > 1 and cols[0] == fld:
                cols.pop(0)
                fldcomments.setdefault(fld, cols)
                tblcomments.pop(i)
                break

    return (tblcomments, fldcomments)


def write_table_comment (fd, table_name, tblcomments):
    util.write_file_utf8(fd, '\n########################################\n')
    util.write_file_utf8(fd, '# %s\n', table_name)

    for comment in tblcomments:
        u16line = comment.strip(",. '\n").strip('#"')
        if len(u16line) > 0:
            utf8line = u16line.encode('utf-8')
            util.write_file_utf8(fd, '# %s\n', utf8line)
        pass

    util.write_file_utf8(fd, '########################################\n')
    pass


def eval_config_varstr (cfgDict, varstr):
    for k, v in cfgDict.items():
        varstr = varstr.replace(str(k), str(v))
    if varstr.find('+') != -1:
        return "%d" % eval(varstr.strip())
    else:
        return varstr.strip()


def field_type_define (fldtype, moduleCfg):
    types = fldtype.split("(")
    typename = types[0].strip()

    typeprefix = field_type_cast[typename]

    if len(types) == 2:
        fldlens = types[1].strip(" ").strip(")").split(',')

        if fldlens == 2:
            precision = eval_config_varstr(moduleCfg, fldlens[0])
            scale = eval_config_varstr(moduleCfg, fldlens[1])

            return "%s(%s,%s)" % (typeprefix, precision, scale)
        else:
            precision = eval_config_varstr(moduleCfg, fldlens[0])

            return "%s(%s)" % (typeprefix, precision)
    else:
        return typeprefix


#######################################################################
def create_phoenix_table (fcresql, dbtable, tabledict, moduleCfg):
    (comment, rowkey, fields) = tabledict.get('comment'), tabledict['rowkey'], tabledict['fields']

    if comment:
        (tblcomments, fldcomments) = parse_table_comment(fields, comment)
        write_table_comment(fcresql, dbtable, tblcomments)

    sql = 'CREATE TABLE IF NOT EXISTS %s (\n' % dbtable

    pkfldlist, outfields = [], []

    # 主键声明必须按次序
    keys = rowkey.split(",")
    for k in keys:
        pkfld = k.strip()
        pkfldlist.append(pkfld)
        outfields.append(pkfld)

    for fldname in fields:
        if fldname not in pkfldlist:
            outfields.append(fldname)

    for fldname in outfields:
        fldtype = fields[fldname]
        fldtypedef = field_type_define(fldtype, moduleCfg)

        if fldname in pkfldlist:
            sql += '  "%s" %s NOT NULL,\n' % (fldname, fldtypedef)
        else:
            sql += '  "%s" %s,\n' % (fldname, fldtypedef)

    if len(pkfldlist) > 0:
        pk_name = dbtable.replace('"','').replace('.','_')
        sql += '  CONSTRAINT pk PRIMARY KEY ("%s")\n' % ('", "'.join(pkfldlist))

    sql += ') SALT_BUCKETS=%s;\n\n' % str(salt_buckets_default)

    util.write_file_utf8(fcresql, sql)

    # 为表和字段添加注释
    if comment:
        (tblcomments, fldcomments) = parse_table_comment(fields, comment)

        table_schem = dbtable.split(".")[0].strip('"')
        table_name = dbtable.split(".")[1].strip('"')

        sql = comment_table_sql(table_schem, table_name, None, False, tblcomments, field_remarks_maxlen)
        if sql:
            util.write_file_utf8(fcresql, sql)
            util.write_file_utf8(fcresql, "\n")

        for fldname in fields:
            if fldname in pkfldlist:
                sql = comment_table_sql(table_schem, table_name, fldname, True, fldcomments.get(fldname), field_remarks_maxlen)
            else:
                sql = comment_table_sql(table_schem, table_name, fldname, False, fldcomments.get(fldname), field_remarks_maxlen)

            if sql:
                util.write_file_utf8(fcresql, sql)
                util.write_file_utf8(fcresql, "\n")
    pass

#######################################################################
def create_phoenix_cresql (dict, modulename, outsqlfile, isforce, moduleCfg):
    (tablespace, tables, uuidtable, uuid_seqs) = dict['tablespace'], dict['tables'], dict['uuid-table'], None

    if uuidtable:
        uuid_seqs = uuidtable.get('fields')

    cresqlfile = outsqlfile.replace('${tablespace}', tablespace).replace('${module}', modulename).strip()

    fcresql = util.open_file(cresqlfile)

    dbheader = '''\
###########################################################
# %s
#   hbase phoenix database create sqlfile
#
# @author: %s
# @version: 2019-03-15 15:45:56
# @create: %s
# @update: 2019-03-15 15:45:56
#
# 用法:
#   $ sqlline.py zkhost:zkport sqlfile
#
###########################################################

''' % (os.path.basename(cresqlfile), dict['author'], dict['version'], dict['create'], util.nowtime())

    util.write_file_utf8(fcresql, dbheader)

    util.info2('create cresql file for hbase-phoenix db: "%s"' % tablespace)

    for tablename in tables:
        dbtable = '"%s"."%s"' % (tablespace, tablename)
        sql = 'DROP TABLE IF EXISTS %s CASCADE;\n' % dbtable
        util.write_file_utf8(fcresql, sql)

    # http://www.cnblogs.com/hbase-community/p/8853573.html
    if uuid_seqs:
        utf16str = uuidtable.get('comment', '%s.uuid.$sequence' % tablespace).strip("#',. \n").strip('"')

        util.write_file_utf8(fcresql, "\n")
        util.write_file_utf8(fcresql, "########################################\n")
        util.write_file_utf8(fcresql, "# %s\n" % utf16str.encode('utf-8'))
        util.write_file_utf8(fcresql, "########################################\n")
        for seq in uuid_seqs:
            seqname = '"%s"."uuid.%s"' % (tablespace, seq)
            sql = 'DROP SEQUENCE IF EXISTS %s;\n' % seqname
            util.write_file_utf8(fcresql, sql)

    if uuid_seqs:
        util.write_file_utf8(fcresql, "\n")
        for seq in uuid_seqs:
            seqname = '"%s"."uuid.%s"' % (tablespace, seq)
            if sequence_is_cycle:
                sql = 'CREATE SEQUENCE IF NOT EXISTS %s START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE %s CYCLE CACHE %s;\n' % (seqname, str(sequence_max_value), str(sequence_cache_number))
            else:
                sql = 'CREATE SEQUENCE IF NOT EXISTS %s START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE %s CACHE %s;\n' % (seqname, str(sequence_max_value), str(sequence_cache_number))
            util.write_file_utf8(fcresql, sql)

    numtables = 0
    for tablename in tables:
        numtables += 1
        dbtable = '"%s"."%s"' % (tablespace, tablename)
        util.info("(%d) create phoenix table: %s" % (numtables, dbtable))
        create_phoenix_table(fcresql, dbtable, tables[tablename], moduleCfg)

    fcresql.close()
    util.remove_bom_header(cresqlfile)

    util.info2("total tables: " + str(numtables))
    util.info2("file created: " + cresqlfile)
    pass


#######################################################################
# main entry function
#
def main(parser, appConfig, loggerConfig):
    import utils.logger

    (options, args) = parser.parse_args(args=None, values=None)

    loggerDictConfig = utils.logger.set_logger(loggerConfig, options.log_path, options.log_level)

    elog.force("%s-%s starting", APPNAME, APPVER)

    # 当前脚本绝对路径
    abspath = util.script_abspath(inspect.currentframe())

    util.print_options_attrs(options, ['source_dbicfg', 'dest_sqlfile'])

    absYamlFile = os.path.abspath(options.source_dbicfg)
    absSqlFile = os.path.abspath(options.dest_sqlfile)

    module, _ = os.path.splitext(os.path.basename(absYamlFile))

    util.info2(absYamlFile)
    util.info2(absSqlFile)

    # 打开配置文件
    fd = open(absYamlFile)
    data = fd.read()
    fd.close()

    # 载入配置
    dict = yaml.load(data)

    # 创建 sqlfile
    create_phoenix_cresql(dict, module.lower(), absSqlFile, options.force, dict.get('constants'))

    util.warn("NOW YOU CAN USE BELOW COMMAND TO CREATE TABLES IN HBASE-PHOENIX !")
    elog.force_clean("  $ sqlline.py zkhost:zkport /path/to/file.cresql")

    util.info("Sample:\n  $ ./sqlline.py localhost:2182 %s" % absSqlFile)
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
        group_options = os.path.join(APPHOME, "options/phoenix_cresql_gen_options.yaml"))

    # 应用程序的缺省配置
    appConfig = {
        "project_rootdir": os.path.dirname(APPHOME),
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
