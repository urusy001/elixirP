import re, httpx

def login_ok(base, user, pwd):
    s = httpx.Client(follow_redirects=True, timeout=20)
    s.get(f"{base}/auth/")  # get cookies
    s.post(f"{base}/auth/?login=yes", data={
        "AUTH_FORM":"Y","TYPE":"AUTH","backurl":"/personal/",
        "USER_LOGIN":user,"USER_PASSWORD":pwd
    })
    me = s.get(f"{base}/personal/").text
    print(me)
    uid = re.search(r'"USER_ID":"([^"]*)"', me)
    print(
        uid.group(1),
    )
    return bool(uid and uid.group(1).isdigit())

print(login_ok("https://elixirpeptide.ru", "urusy001", "RusTNTisamouse11"))