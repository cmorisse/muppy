import os
import gitlab
import gitlab_driver


user = os.environ.get('AUDAXIS_GITLAB_USERNAME')
password = os.environ.get('AUDAXIS_GITLAB_PASSWORD')

#gl = gitlab.Gitlab('https://gitlab.audaxis.com', email=user, password=password, api_version=4)
#gl = gitlab.Gitlab('https://gitlab.audaxis.com', 'mmgc-1Qesz3W-zxUQ4jm', api_version=4)

# make an API request to create the gl.user object. This is mandatory if you
# use the username/password authentication.
#gl.auth()

#print(gl.projects.list())

gl_repo = gitlab_driver.GitlabRepository('', password, 'git git@gitlab.audaxis.com:openerp/appserver-ag.git', '/opt/openerp/ambigroup')


muppy_test_key_name = "user@dummysrv"
muppy_test_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDB1naSZtTku4rHGEBSWfSYqC2uAMnBBlHZ2ruqOQdQQjpbiJrpxJ1rZxnKIYTctRBe5twl2f+RMZoKnVB69lAlv1i90NKIkYprHd+ZKPvssDY2TwYre3LqO3/Rxua4DdalOwwSq4FvX3zDpQoRkJoW4SPD6Iz1WrmwuGhNoAD+rSYnFaeVtjPMjhX2pt9Hc09kp8gDONftGClmIsUQxPcazJ3Bu18zld9Ls/twlYOFOIg/WF2oQh+xXuBpWlIagnW1F0IrpXYwOt9+apLYpMUhVOhkgDEXiRUJYpP9iU8m6AU2EpVb0T01lxK114Tx+xU2ETkzyPQmaF1kTESGafWb user@dummysrv"


a_key = gl_repo.search_deployment_key(muppy_test_key_name)
if a_key:
    print("%s key found. Deleting it before recreating it." % muppy_test_key_name)
    response = gl_repo.delete_deployment_key(a_key[0])
else:
    print("%s key not found, creating one" % muppy_test_key_name)
    response = gl_repo.post_deployment_key(muppy_test_key_name, muppy_test_key)


print("that's all folks")
