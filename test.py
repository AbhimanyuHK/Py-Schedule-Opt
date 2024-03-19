# # inter
#
# class A:
#
#     def x(self):
#         print("part of class A")
#
#
# class B(A):
#
#     def __init__(self):
#         super(B, self).__init__()
#
#     def y(self):
#         print("part of class B")
#
#     # def x(self):
#     #     print("part of class B")
#
#
# A().x()
# print()
# B().x()


# import boto3
# from numpy import NaN
#
# client = boto3.client("S3")
#
# client.put_object("fullpath/file_name", "file")
#
# client.get_object("file_name")
#
# client.list_object("path")
#
# aws cli ec2 --instance yuyu enable


import pandas as pd
from numpy import NaN


json = [{"A": None, "B": "", "C": NaN}]
df = pd.DataFrame(json)

print(df.isnull())

