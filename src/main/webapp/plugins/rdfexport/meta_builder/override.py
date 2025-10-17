def override(*, type: str, role: str, phase: str, target: str | None = None):
    def wrap(fn):
        t = target
        if t is None:
            n = fn.__name__
            for suf in ("_new", "_override", "_ovr"):
                if n.endswith(suf):
                    n = n[: -len(suf)]
                    break
            t = n
        fn.__override__ = (type, role, phase)
        fn.__override_target__ = t
        return fn
    return wrap
