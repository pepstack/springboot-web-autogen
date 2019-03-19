# springboot-web-autogen
autogen springboot2 website

这是一套 python 脚本，用于自动生成基于 springboot2 的 java web 服务。

持续更新中。

目前完成：

    - 根据配置文件 (yaml) 自动生成 hbase-phoenix 数据库表的自动创建语句 (cresql)

        $ phoenix_cresql_gen.py --help

    src/
        main/
            java/
                com/
                    pepstack/
                        webapp/
                            controller/
                            model/
            resources/
                static/
                    css/
                    js/
                templates/
        test/
            java/
                com/
                    pepstack/
