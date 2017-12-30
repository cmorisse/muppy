import os
import requests


user = os.environ.get('AUDAXIS_GITLAB_USERNAME')
password = os.environ.get('AUDAXIS_GITLAB_PASSWORD')

API_URL = "https://gitlab.audaxis.com/api/v4"


HEADERS = {
    'PRIVATE-TOKEN': password,
}



### list keys of project 92

URL = "%s/%s" % (API_URL, "projects/92/deploy_keys")
resp = requests.get(URL, 
                    headers=HEADERS)

print("Response: %s" % resp)
#print("Response content: %s" % resp.text)

for k in resp.json():
    print k['title']
    
    
### Add a key on project 92
print "###################### Adding key"
muppy_test_key_title = "user@dummysrv"
muppy_test_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDB1naSZtTku4rHGEBSWfSYqC2uAMnBBlHZ2ruqOQdQQjpbiJrpxJ1rZxnKIYTctRBe5twl2f+RMZoKnVB69lAlv1i90NKIkYprHd+ZKPvssDY2TwYre3LqO3/Rxua4DdalOwwSq4FvX3zDpQoRkJoW4SPD6Iz1WrmwuGhNoAD+rSYnFaeVtjPMjhX2pt9Hc09kp8gDONftGClmIsUQxPcazJ3Bu18zld9Ls/twlYOFOIg/WF2oQh+xXuBpWlIagnW1F0IrpXYwOt9+apLYpMUhVOhkgDEXiRUJYpP9iU8m6AU2EpVb0T01lxK114Tx+xU2ETkzyPQmaF1kTESGafWb user@dummysrv"
payload = {
    "key": muppy_test_key,
    "title": muppy_test_key_title,
    "id": 92,
    "can_push": False
}

URL = "%s/%s" % (API_URL, "projects/92/deploy_keys")
resp = requests.post(URL,
                     json=payload,
                     headers=HEADERS)

print("Response: %s" % resp)
#print("Response content: %s" % resp.text)

resp_json = resp.json()
print resp_json
