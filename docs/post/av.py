class av(xr.NodeTransformer):
    def __init__(rk, pz: ae, jv: aa) -> None:
        rk.dl = pz.lt
        rk.dn: dict[str, str] = {ws: ko for ko, ws in pz.lt.items()}
        rk.df = set(jv.ox)
        rk.de = set(jv.ow)
        rk.cu = {pz.lt.get(mr, mr) for mr in rk.df}
        rk.ct = {pz.lt.get(mr, mr) for mr in rk.de}
        rk.by = set(jv.ig)
        rk.cn = set(pz.lc)
        rk.ce: dict[str, str] = {}
        rk.bx: set[str] = set()
        rk.ba: int = 0
        rk.bg: set[str] = set(jv.py)
        rk.bg.update(pz.lt.keys())
        rk.bg.update(pz.lt.values())
        rk.bg.update(jv.ig)
        rk.bg.update(xt.kwlist)
        rk.bg.update(dir(xs))
        rk.cx: list[dict[str, str]] = [{}]
        rk.sp: int = 0
        rk.lb: int = 0
        rk.hl: int = 0
    def xi(rk, my: xr.Name) -> xr.AST:
        qe = rk.cs(my.id)
        if my.id in rk.ce:
            qe = rk.ce[my.id]
        if qe is None:
            return my
        if my.id in rk.by and my.id not in rk.ce:
            return my
        if qe != my.id:
            rk.sp += 1
            return xr.copy_location(xr.Name(id=qe, ctx=my.ctx), my)
        return my
    def xe(rk, my: xr.Import) -> xr.AST:
        wq: list[xr.alias] = []
        fy = False
        for ep in my.names:
            if ep.asname is not None:
                wq.append(ep)
                continue
            if "." in ep.name:
                wq.append(ep)
                continue
            ie = ep.name
            qe = rk.ce.get(ie)
            if qe is None:
                qe = rk.cy()
                rk.ce[ie] = qe
            if ie in rk.by:
                rk.bx.add(qe)
            wq.append(xr.alias(mr=ep.name, asname=qe))
            fy = True
            rk.sp += 1
        if not fy:
            return my
        return xr.copy_location(xr.Import(names=wq), my)
    def xk(rk, my: xr.alias) -> xr.AST:
        if "." in my.name:
            return my
        qe = rk.cs(my.name)
        if qe is None or qe == my.name:
            return my
        rk.sp += 1
        return xr.copy_location(xr.alias(mr=qe, asname=my.asname), my)
    def xl(rk, my: xr.arg) -> xr.AST:
        wp = rk.generic_visit(my)
        if not isinstance(wp, xr.arg):
            return wp
        qe = rk.cs(wp.arg)
        if qe is None or qe == wp.arg:
            return wp
        rk.sp += 1
        return xr.copy_location(
            xr.arg(arg=qe, annotation=wp.annotation, type_comment=wp.type_comment), wp
        )
    def xc(rk, my: xr.FunctionDef) -> xr.AST:
        rk.di()
        rk.dt(my.args)
        wp = rk.generic_visit(my)
        rk.dc()
        if not isinstance(wp, xr.FunctionDef):
            return wp
        qe = rk.cs(wp.name)
        if qe is None or qe == wp.name:
            return wp
        rk.sp += 1
        return xr.copy_location(
            wp.__class__(
                name=qe,
                args=wp.args,
                body=wp.body,
                decorator_list=wp.decorator_list,
                returns=wp.returns,
                type_comment=wp.type_comment,
            ),
            wp,
        )
    def ww(rk, my: xr.AsyncFunctionDef) -> xr.AST:
        rk.di()
        rk.dt(my.args)
        wp = rk.generic_visit(my)
        rk.dc()
        if not isinstance(wp, xr.AsyncFunctionDef):
            return wp
        qe = rk.cs(wp.name)
        if qe is None or qe == wp.name:
            return wp
        rk.sp += 1
        return xr.copy_location(
            wp.__class__(
                name=qe,
                args=wp.args,
                body=wp.body,
                decorator_list=wp.decorator_list,
                returns=wp.returns,
                type_comment=wp.type_comment,
            ),
            wp,
        )
    def xg(rk, my: xr.Lambda) -> xr.AST:
        rk.di()
        rk.dt(my.args)
        wp = rk.generic_visit(my)
        rk.dc()
        return wp
    def wz(rk, my: xr.ClassDef) -> xr.AST:
        rk.di()
        wp = rk.generic_visit(my)
        rk.dc()
        if not isinstance(wp, xr.ClassDef):
            return wp
        qe = rk.cs(wp.name)
        if qe is None or qe == wp.name:
            return wp
        rk.sp += 1
        return xr.copy_location(
            wp.__class__(
                name=qe,
                bases=wp.bases,
                keywords=wp.keywords,
                body=wp.body,
                decorator_list=wp.decorator_list,
            ),
            wp,
        )
    def wx(rk, my: xr.Attribute) -> xr.AST:
        wp = rk.generic_visit(my)
        if not isinstance(wp, xr.Attribute):
            return wp
        ki = wp.attr in rk.de
        kj = wp.attr in rk.df
        if not ki and (not kj):
            return wp
        qe = rk.cs(wp.attr)
        if qe is None or qe == wp.attr:
            return wp
        nw = rk.bf(wp.value)
        if nw == "external":
            return wp
        if nw == "likely_local":
            rk.lb += 1
        rk.sp += 1
        return xr.copy_location(xr.Attribute(value=wp.value, attr=qe, ctx=wp.ctx), wp)
    def wy(rk, my: xr.Call) -> xr.AST:
        wp = rk.generic_visit(my)
        if not isinstance(wp, xr.Call):
            return wp
        rm = rk.dw(wp.func)
        qb = list(wp.keywords)
        kq = False
        if rm:
            for jv, kp in enumerate(qb):
                if kp.arg is None:
                    continue
                kr = rk.cs(kp.arg)
                if kr is None or kr == kp.arg:
                    continue
                qb[jv] = xr.keyword(arg=kr, value=kp.value)
                rk.sp += 1
                kq = True
            if kq:
                rk.lb += 1
        if kq:
            wp = xr.copy_location(xr.Call(func=wp.func, args=wp.args, keywords=qb), wp)
        fu = bk(wp.func)
        if fu not in ap or len(wp.args) < 2:
            return wp
        nm = wp.args[0]
        ms = wp.args[1]
        if not isinstance(ms, xr.Constant) or not isinstance(ms.value, str):
            return wp
        fd = ms.value
        if fd not in rk.de:
            return wp
        qe = rk.cs(fd)
        if qe is None or qe == fd:
            return wp
        nw = rk.bf(nm)
        if nw == "external":
            return wp
        if nw == "likely_local":
            rk.lb += 1
        qd = xr.Constant(value=qe)
        mv = list(wp.args)
        mv[1] = qd
        rk.hl += 1
        rk.sp += 1
        return xr.copy_location(
            xr.Call(func=wp.func, args=mv, keywords=wp.keywords), wp
        )
    def wu(rk, my: xr.Assign) -> xr.AST:
        wp = rk.generic_visit(my)
        if not isinstance(wp, xr.Assign):
            return wp
        nw = rk.ch(wp.value)
        if nw is None:
            return wp
        for st in wp.targets:
            if isinstance(st, xr.Name):
                rk.dk(st.id, nw)
        return wp
    def xb(rk, my: xr.For) -> xr.AST:
        nw = rk.cg(my.iter)
        if nw is not None:
            rk.be(my.target, nw)
        return rk.generic_visit(my)
    def wv(rk, my: xr.AsyncFor) -> xr.AST:
        nw = rk.cg(my.iter)
        if nw is not None:
            rk.be(my.target, nw)
        return rk.generic_visit(my)
    def xm(rk, my: xr.comprehension) -> xr.AST:
        nw = rk.cg(my.iter)
        if nw is not None:
            rk.be(my.target, nw)
        return rk.generic_visit(my)
    def xh(rk, my: xr.ListComp) -> xr.AST:
        rk.du(my.generators)
        return rk.generic_visit(my)
    def xj(rk, my: xr.SetComp) -> xr.AST:
        rk.du(my.generators)
        return rk.generic_visit(my)
    def xd(rk, my: xr.GeneratorExp) -> xr.AST:
        rk.du(my.generators)
        return rk.generic_visit(my)
    def xa(rk, my: xr.DictComp) -> xr.AST:
        rk.du(my.generators)
        return rk.generic_visit(my)
    def wt(rk, my: xr.AnnAssign) -> xr.AST:
        wp = rk.generic_visit(my)
        if not isinstance(wp, xr.AnnAssign):
            return wp
        nw: str | None = None
        if wp.value is not None:
            nw = rk.ch(wp.value)
        if nw is None:
            nw = rk.bd(wp.annotation)
        if nw is None:
            return wp
        if isinstance(wp.target, xr.Name):
            rk.dk(wp.target.id, nw)
        return wp
    def cs(rk, mr: str) -> str | None:
        if mr.startswith("__") and mr.endswith("__"):
            return None
        return rk.dl.get(mr)
    def bf(rk, ws: xr.expr) -> str:
        if isinstance(ws, xr.Name):
            wh = rk.cd(ws.id)
            if wh is not None:
                return wh
            if ws.id in rk.cn:
                return "likely_local"
            if ws.id in rk.by:
                return "external"
            if ws.id in rk.bx:
                return "external"
            if ws.id in rk.ce.values():
                return "project"
            if ws.id == "self":
                return "project"
            return "external"
        return "likely_local"
    def cy(rk) -> str:
        while True:
            ep = bb(rk.ba)
            rk.ba += 1
            if ep in rk.bg:
                continue
            if ep in rk.ce.values():
                continue
            return ep
    def dw(rk, ja: xr.expr) -> bool:
        if isinstance(ja, xr.Name):
            if ja.id in rk.by or ja.id in rk.bx:
                return False
            if ja.id in rk.df or ja.id in rk.cu:
                return True
            return ja.id in rk.dl or ja.id in rk.dl.values()
        if isinstance(ja, xr.Attribute):
            return (
                ja.attr in rk.de
                or ja.attr in rk.ct
                or ja.attr in rk.df
                or (ja.attr in rk.cu)
            )
        return False
    def di(rk) -> None:
        rk.cx.append({})
    def dc(rk) -> None:
        if len(rk.cx) > 1:
            rk.cx.pop()
    def dv(rk, mr: str, nw: str) -> None:
        rk.cx[-1][mr] = nw
    def cd(rk, mr: str) -> str | None:
        for rb in reversed(rk.cx):
            if mr in rb:
                return rb[mr]
        return None
    def ch(rk, ws: xr.expr) -> str | None:
        if isinstance(ws, xr.Name):
            wh = rk.cd(ws.id)
            if wh is not None:
                return wh
            if ws.id in rk.cn:
                return "likely_local"
            return None
        if not isinstance(ws, xr.Call):
            return None
        ja = ws.func
        if isinstance(ja, xr.Name):
            if ja.id in rk.by or ja.id in rk.bx:
                return "external"
            if ja.id == "enumerate":
                if ws.args:
                    return rk.cg(ws.args[0])
                return None
            if ja.id in {"sorted", "list", "tuple", "set", "reversed"}:
                if ws.args:
                    return rk.cg(ws.args[0])
                return None
            if ja.id in rk.df or ja.id in rk.cu:
                return "project"
            if ja.id in rk.dl or ja.id in rk.dl.values():
                return "likely_local"
            return None
        if isinstance(ja, xr.Attribute):
            nv = rk.bf(ja.value)
            if nv == "external":
                return "external"
            if ja.attr in rk.df or ja.attr in rk.cu:
                return "project"
            if nv in {"project", "likely_local"} and (
                ja.attr in rk.de or ja.attr in rk.ct
            ):
                return "likely_local"
            return None
        return None
    def cg(rk, kn: xr.expr) -> str | None:
        if isinstance(kn, xr.Name):
            return rk.cd(kn.id)
        if isinstance(kn, xr.Call):
            return rk.ch(kn)
        if isinstance(kn, xr.Subscript):
            return rk.cg(kn.value)
        if isinstance(kn, xr.Attribute):
            nv = rk.bf(kn.value)
            if nv == "external":
                return "external"
            if (
                kn.attr in rk.de
                or kn.attr in rk.ct
                or kn.attr in rk.df
                or (kn.attr in rk.cu)
            ):
                return "likely_local"
            return nv
        return None
    def be(rk, st: xr.expr, nw: str) -> None:
        if isinstance(st, xr.Name):
            rk.dk(st.id, nw)
            return
        if isinstance(st, (xr.Tuple, xr.List)):
            for hq in st.elts:
                rk.be(hq, nw)
    def du(rk, jj: list[xr.comprehension]) -> None:
        for ji in jj:
            nw = rk.cg(ji.iter)
            if nw is None:
                continue
            rk.be(ji.target, nw)
    def dt(rk, fa: xr.arguments) -> None:
        for fb in rk.cm(fa):
            if fb.arg == "self":
                rk.dj(fb.arg, "project")
                continue
            if fb.arg == "cls":
                rk.dj(fb.arg, "project")
                continue
            if fb.annotation is None:
                rk.dj(fb.arg, "likely_local")
                continue
            ex = rk.bd(fb.annotation)
            if ex is None:
                continue
            rk.dj(fb.arg, ex)
    def dj(rk, ez: str, nw: str) -> None:
        rk.dk(ez, nw)
    def dk(rk, mr: str, nw: str) -> None:
        rk.dv(mr, nw)
        ls = rk.cs(mr)
        if ls is not None:
            rk.dv(ls, nw)
        nn = rk.dn.get(mr)
        if nn is not None:
            rk.dv(nn, nw)
    def bd(rk, ew: xr.expr) -> str | None:
        mt: set[str] = {my.id for my in xr.walk(ew) if isinstance(my, xr.Name)}
        if mt & rk.df:
            return "project"
        if mt & rk.cu:
            return "project"
        if mt:
            return "external"
        return None
    def cm(rk, fa: xr.arguments) -> list[xr.arg]:
        gi = list(fa.posonlyargs)
        gi.extend(fa.args)
        if fa.vararg is not None:
            gi.append(fa.vararg)
        gi.extend(fa.kwonlyargs)
        if fa.kwarg is not None:
            gi.append(fa.kwarg)
        return gi