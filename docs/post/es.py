def es(oy: Path, it: list[Path]) -> aa:
    lo = dg(oy=oy, it=it)
    py: set[str] = set()
    ig: set[str] = set()
    ox: set[str] = set()
    ow: set[str] = set()
    la: set[str] = set()
    for rw in sorted(it):
        try:
            rt = rw.read_text(encoding="utf-8")
            mo = xr.parse(rt)
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            lq.warning(
                "Skipping file during analysis due to parse/read failure",
                extra={"path": str(rw), "error": str(exc)},
            )
            continue
        gj = aw(lo=lo)
        gj.visit(mo)
        py.update(gj.py)
        ig.update(gj.ig)
        ox.update(gj.ox)
        ow.update(gj.ow)
        la.update(gj.la)
    py.difference_update(ig)
    return aa(
        py=frozenset(py),
        ig=frozenset(ig),
        ox=frozenset(ox),
        ow=frozenset(ow),
        la=frozenset(la),
    )