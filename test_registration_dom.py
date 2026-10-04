import re

def verify_dom_and_js():
    with open("static/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    with open("static/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    checks = [
        ('createAccountLink ID in HTML', 'id="createAccountLink"' in html),
        ('auth-role-tabs removed from HTML', 'class="auth-role-tabs"' not in html),
        ('tabRoleCitizen removed from HTML', 'id="tabRoleCitizen"' not in html),
        ('tabRoleAdmin removed from HTML', 'id="tabRoleAdmin"' not in html),
        ('modalCreateAccountSelection in HTML', 'id="modalCreateAccountSelection"' in html),
        ('selectRoleCitizenCard in HTML', 'id="selectRoleCitizenCard"' in html),
        ('selectRoleWorkerCard in HTML', 'id="selectRoleWorkerCard"' in html),
        ('selectRoleSupervisorCard in HTML', 'id="selectRoleSupervisorCard"' in html),
        ('No Admin option in Create Account modal', 'Continue as Admin' not in html and 'Register Admin' not in html),
        ('modalCitizenRegister in HTML', 'id="modalCitizenRegister"' in html),
        ('formCitizenRegister in HTML', 'id="formCitizenRegister"' in html),
        ('modalWorkerRegister in HTML', 'id="modalWorkerRegister"' in html),
        ('formWorkerRegister in HTML', 'id="formWorkerRegister"' in html),
        ('modalSupervisorRegister in HTML', 'id="modalSupervisorRegister"' in html),
        ('formSupervisorRegister in HTML', 'id="formSupervisorRegister"' in html),
        ('openCreateAccountModal function in JS', 'function openCreateAccountModal' in js),
        ('toggleCreateAccountModal function in JS', 'function toggleCreateAccountModal' in js),
        ('selectRegistrationType function in JS', 'function selectRegistrationType' in js),
        ('openCitizenRegistration function in JS', 'function openCitizenRegistration' in js),
        ('openWorkerRegistration function in JS', 'function openWorkerRegistration' in js),
        ('openSupervisorRegistration function in JS', 'function openSupervisorRegistration' in js),
        ('setupAuthEventListeners attached', 'setupAuthEventListeners()' in js),
        ('openCreateAccountModal exported to window', 'window.openCreateAccountModal = openCreateAccountModal' in js),
        ('toggleCreateAccountModal exported to window', 'window.toggleCreateAccountModal = toggleCreateAccountModal' in js),
        ('selectRegistrationType exported to window', 'window.selectRegistrationType = selectRegistrationType' in js),
        ('openCitizenRegistration exported to window', 'window.openCitizenRegistration = openCitizenRegistration' in js),
        ('openWorkerRegistration exported to window', 'window.openWorkerRegistration = openWorkerRegistration' in js),
        ('openSupervisorRegistration exported to window', 'window.openSupervisorRegistration = openSupervisorRegistration' in js),
    ]

    all_passed = True
    print("=================== DOM & JS VERIFICATION CHECKS ===================")
    for name, passed in checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    print("====================================================================")
    assert all_passed, "Some DOM/JS verification checks failed!"
    print("ALL DOM & JS VERIFICATION CHECKS PASSED!")

if __name__ == "__main__":
    verify_dom_and_js()
