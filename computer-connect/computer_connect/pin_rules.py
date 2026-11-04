"""Pure validation and distribution for six-digit pairing codes."""
def distribute(current, index, value):
    """Pure edit rule shared by typing/paste. Reject, never sanitize, bad input."""
    if not isinstance(value,str) or any(c not in '0123456789' for c in value):
        raise ValueError('PIN contains only six ASCII digits')
    if len(value)>6 or not 0<=index<6 or len(current)!=6:
        raise ValueError('Invalid PIN edit')
    result=list(current)
    if len(value)==6:
        result=list(value);return result,5
    if not value:
        result[index]='';return result,index
    if index+len(value)>6:
        raise ValueError('PIN paste exceeds six digits')
    for offset,char in enumerate(value):result[index+offset]=char
    return result,min(5,index+len(value))

