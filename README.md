# binance-abrupt-monitoring
共享用，虽然是public但是大家请不要folk或者star，谢谢理解
This Repo is only for sharing documents.
Please do not folk or star, thanks!


#**说明**#

一，环境准备

1.安装python（如有就跳过）

直接访问https://www.python.org/downloads/
下载最新版python, 安装的时候记得选添加到PATH和赋予管理员权限

2.安装币安python库
在cmd或者powershell

执行pip install python-binance



二，替换apikey和密钥

connectiontest-binance.py里的第七行和第八行替换成自己币安的API KEY，发行方法如下
https://www.binance.com/en-JP/support/faq/detail/360002502072
(不好意思我不知道为什么我这里只有英文和日文的 我感觉肯定有中文的,可能是我IP问题)


三，运行程序

用vscode等IDE可以直接运行，也可以命令栏里python connectiontest-binance.py运行
程序默认五分钟自动执行一次，按ctrl+c可以终止

