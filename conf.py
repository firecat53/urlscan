URLINTERNALPATTERN = r'[{}()@\w/\\\-%?!&.=:;+,#~]'
URLTRAILINGPATTERN = r'[{}(@\w/\-%&=+#]'
HTTPURLPATTERN = (r'(?:(https?|file|ftps?)://' + URLINTERNALPATTERN + r'*' + URLTRAILINGPATTERN + r')')
