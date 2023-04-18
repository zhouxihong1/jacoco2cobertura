# jacoco2cobertura
用于将 jacoco xml 转化为 cobertura的python脚本
A script for converting JaCoCo XML coverage reports into Cobertura XML coverage reports.


首先感谢: https://github.com/rix0rrr/cover2cover
该项目,
没有他就没有本项目
其次在该项目中做了如下优化:
1. 语法全面支持Python3
2. 优化ElementTree的tostring方法decode
3. 优化变量名,消除PEP8规范下的警告
4. 优化Usage用法描述
5. 添加 OUTPUT_PATH, 可直接将Cobertura输出文件(原有命令行>>输出也兼容)
6. 添加 --xml-pretty参数,使输出的Cobertura内容更易读
7. 新增 only --xml-pretty模式, 用于直接打印xml,而不进行 jacoco xml -> Cobertura的转义
8. 新增入口部分函数注释
