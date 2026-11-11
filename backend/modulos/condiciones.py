"""
Minilenguaje de condiciones (modulos.md §3). Analizador descendente recursivo propio: sin `eval`,
`ast`, `compile` ni atributos de Python. Falla cerrada: un operando ausente o de otro tipo hace
falsa la comparación y se anota en el informe.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from . import campos_momento as cm

MAX_LONGITUD, MAX_PROFUNDIDAD, MAX_NODOS = 300, 12, 40
FUNCIONES = ("largo", "abs", "min", "max")
PALABRAS = {"y", "o", "no", "en", "verdadero", "falso"}


class ErrorCondicion(ValueError):
    pass


_TOKEN = re.compile(
    r"""\s*(?:
      (?P<num>\d+(?:\.\d+)?)
     |(?P<str>"[^"\n]*"|'[^'\n]*')
     |(?P<id>[^\W\d]\w*)
     |(?P<op>==|!=|<=|>=|[<>+\-*(),.\[\]])
    )""",
    re.VERBOSE,
)


def _tokens(texto: str) -> list[tuple[str, str]]:
    salida, pos = [], 0
    texto = texto.rstrip()
    while pos < len(texto):
        m = _TOKEN.match(texto, pos)
        if not m or m.end() == pos:
            raise ErrorCondicion(f"Carácter no permitido en la posición {pos}: {texto[pos:pos + 10]!r}.")
        tipo = m.lastgroup
        salida.append((tipo, m.group(tipo)))
        pos = m.end()
    return salida


class _Parser:
    def __init__(self, texto: str):
        if not isinstance(texto, str) or not texto.strip():
            raise ErrorCondicion("La condición está vacía.")
        if len(texto) > MAX_LONGITUD:
            raise ErrorCondicion(f"La condición supera {MAX_LONGITUD} caracteres.")
        self.t = _tokens(texto)
        self.i = 0
        self.nodos = 0
        self.prof = 0

    def _nodo(self, n):
        self.nodos += 1
        if self.nodos > MAX_NODOS:
            raise ErrorCondicion(f"La condición supera {MAX_NODOS} nodos.")
        return n

    def _ver(self, k: int = 0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def _es(self, valor, k=0):
        tipo, v = self._ver(k)
        return v == valor and tipo in ("op", "id")

    def _tomar(self):
        tok = self._ver()
        self.i += 1
        return tok

    def _esperar(self, valor):
        if not self._es(valor):
            raise ErrorCondicion(f"Se esperaba {valor!r}.")
        self.i += 1

    def parse(self):
        arbol = self._expr()
        if self.i != len(self.t):
            raise ErrorCondicion(f"Sobra texto: {self._ver()[1]!r}.")
        return arbol

    def _entrar(self):
        self.prof += 1
        if self.prof > MAX_PROFUNDIDAD:
            raise ErrorCondicion(f"Demasiado anidada (máximo {MAX_PROFUNDIDAD}).")

    def _expr(self):
        self._entrar()
        try:
            return self._o()
        finally:
            self.prof -= 1

    def _o(self):
        n = self._y()
        while self._es("o"):
            self.i += 1
            n = self._nodo(("o", n, self._y()))
        return n

    def _y(self):
        n = self._no()
        while self._es("y"):
            self.i += 1
            n = self._nodo(("y", n, self._no()))
        return n

    def _no(self):
        if self._es("no"):
            self.i += 1
            self._entrar()
            try:
                return self._nodo(("no", self._no()))
            finally:
                self.prof -= 1
        return self._cmp()

    def _cmp(self):
        n = self._suma()
        tipo, v = self._ver()
        if tipo == "op" and v in ("==", "!=", "<", "<=", ">", ">="):
            self.i += 1
            return self._nodo(("cmp", v, n, self._suma()))
        if tipo == "id" and v == "en":
            self.i += 1
            return self._nodo(("cmp", "en", n, self._suma()))
        if tipo == "id" and v == "no" and self._es("en", 1):
            self.i += 2
            return self._nodo(("cmp", "no en", n, self._suma()))
        return n

    def _suma(self):
        n = self._prod()
        while self._ver()[0] == "op" and self._ver()[1] in ("+", "-"):
            op = self._tomar()[1]
            n = self._nodo(("bin", op, n, self._prod()))
        return n

    def _prod(self):
        n = self._unario()
        while self._es("*"):
            self.i += 1
            n = self._nodo(("bin", "*", n, self._unario()))
        return n

    def _unario(self):
        if self._es("-"):
            self.i += 1
            self._entrar()
            try:
                return self._nodo(("neg", self._unario()))
            finally:
                self.prof -= 1
        return self._atomo()

    def _atomo(self):
        tipo, v = self._ver()
        if tipo is None:
            raise ErrorCondicion("La condición termina antes de tiempo.")
        if tipo == "num":
            self.i += 1
            return self._nodo(("lit", Decimal(v)))
        if tipo == "str":
            self.i += 1
            return self._nodo(("lit", v[1:-1]))
        if tipo == "op" and v == "(":
            self.i += 1
            n = self._expr()
            self._esperar(")")
            return n
        if tipo == "op" and v == "[":
            self.i += 1
            elems = []
            if not self._es("]"):
                elems.append(self._expr())
                while self._es(","):
                    self.i += 1
                    elems.append(self._expr())
            self._esperar("]")
            return self._nodo(("lista", tuple(elems)))
        if tipo == "id":
            if v in ("verdadero", "falso"):
                self.i += 1
                return self._nodo(("lit", v == "verdadero"))
            if v in FUNCIONES and self._es("(", 1):
                self.i += 2
                args = []
                if not self._es(")"):
                    args.append(self._expr())
                    while self._es(","):
                        self.i += 1
                        args.append(self._expr())
                self._esperar(")")
                return self._nodo(("llamada", v, tuple(args)))
            if v in ("momento", "modelo"):
                return self._ruta()
            raise ErrorCondicion(f"Palabra no permitida: {v!r}.")
        raise ErrorCondicion(f"Símbolo inesperado: {v!r}.")

    def _ruta(self):
        raiz = self._tomar()[1]
        partes: list[Any] = []
        while True:
            if self._es("."):
                self.i += 1
                tipo, v = self._tomar()
                if tipo != "id" or v in PALABRAS or v.startswith("_"):
                    raise ErrorCondicion(f"Campo no válido en la ruta: {v!r}.")
                partes.append(v)
            elif self._es("["):
                self.i += 1
                tipo, v = self._tomar()
                if tipo != "num" or "." in v:
                    raise ErrorCondicion("Los índices deben ser enteros.")
                self._esperar("]")
                partes.append(int(v))
            else:
                break
        _validar_ruta(raiz, partes)
        return self._nodo(("ruta", raiz, tuple(partes)))


def _validar_ruta(raiz: str, partes: list[Any]) -> None:
    ruta = ".".join([raiz] + [str(p) for p in partes])
    if not partes or not isinstance(partes[0], str):
        raise ErrorCondicion(f"Ruta no permitida: {ruta!r}.")
    p0 = partes[0]
    if raiz == "momento":
        if p0 == "datos":
            ok = len(partes) >= 2 and isinstance(partes[1], str)
        else:
            ok = p0 in cm.RUTAS_MOMENTO and len(partes) == 1
    elif p0 == "perfil":
        ok = len(partes) == 2 and partes[1] in cm.RUTAS_PERFIL
    else:
        ok = p0 in cm.RUTAS_MODELO
    if not ok:
        raise ErrorCondicion(f"Ruta no permitida: {ruta!r}.")


def compilar(texto: str):
    """Texto -> árbol. Lanza `ErrorCondicion` si la sintaxis o las rutas no son válidas."""
    return _Parser(texto).parse()


def rutas_usadas(arbol) -> list[str]:
    """Rutas (`momento.datos.faltan`, ...) que toca un árbol ya compilado."""
    salida: list[str] = []

    def ir(n):
        if not isinstance(n, tuple):
            return
        if n and n[0] == "ruta":
            salida.append(".".join([n[1]] + [str(p) for p in n[2]]))
            return
        for x in n:
            if isinstance(x, tuple):
                ir(x)

    ir(arbol)
    return salida


# --- Evaluación --------------------------------------------------------------------------------

def _num(x):
    """Convierte a Decimal lo numérico; None si no lo es (bool no es número)."""
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int, float)):
        return Decimal(str(x))
    if isinstance(x, str):
        try:
            return Decimal(x.strip())
        except InvalidOperation:
            return None
    return None


def _normalizar(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    return v


def _resolver(raiz: str, partes, ctx: dict):
    v: Any = ctx.get(raiz)
    for p in partes:
        if v is None:
            return None
        if isinstance(p, int):
            if isinstance(v, (list, tuple)) and -len(v) <= p < len(v):
                v = v[p]
            else:
                return None
        elif isinstance(v, dict):
            v = v.get(p)
        else:
            return None
    return _normalizar(v)


def contexto(momento, modelo) -> dict:
    """Diccionario de solo lectura sobre el que se evalúa. Deja fuera lo que el lenguaje no admite."""
    m = momento.model_dump(mode="python", exclude={"contexto_personal", "movimientos", "explicacion"})
    mod = None
    if modelo is not None:
        d = modelo.model_dump(mode="python")
        mod = {k: d.get(k) for k in cm.RUTAS_MODELO}
        # Lo que el usuario cuenta de sus amigos en el chat solo sirve para sus recordatorios (curva-amigos §2.1):
        # nunca para las condiciones de los módulos del banco.
        mod["hechos_aprendidos"] = [h for h in (mod.get("hechos_aprendidos") or []) if h.get("origen") != "chat"]
        perfil = d.get("perfil")
        mod["perfil"] = None if perfil is None else {k: perfil.get(k) for k in cm.RUTAS_PERFIL}
    return {"momento": m, "modelo": mod}


def _anotar(informe, texto):
    if informe is not None:
        informe.append(texto)


def _igual(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None and not (isinstance(a, str) and isinstance(b, str)):
        return na == nb
    return a == b


def _comparar(op, a, b, informe):
    if a is None or b is None:
        _anotar(informe, f"operando ausente en {op!r}")
        return False
    if op in ("en", "no en"):
        if isinstance(b, (list, tuple)):
            dentro = any(_igual(a, x) for x in b)
        elif isinstance(b, str) and isinstance(a, str):
            dentro = a in b
        else:
            _anotar(informe, "tipos no comparables")
            return False
        return dentro if op == "en" else not dentro
    if op in ("==", "!="):
        r = _igual(a, b)
        return r if op == "==" else not r
    if isinstance(a, str) and isinstance(b, str) and (_num(a) is None or _num(b) is None):
        x, y = a, b  # fechas ISO: comparables como texto
    else:
        x, y = _num(a), _num(b)
        if x is None or y is None:
            _anotar(informe, "tipos no comparables")
            return False
    return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]


def _ev(n, ctx, informe):
    t = n[0]
    if t == "lit":
        return n[1]
    if t == "lista":
        return [_ev(x, ctx, informe) for x in n[1]]
    if t == "ruta":
        return _resolver(n[1], n[2], ctx)
    if t == "o":
        return bool(_ev(n[1], ctx, informe)) or bool(_ev(n[2], ctx, informe))
    if t == "y":
        return bool(_ev(n[1], ctx, informe)) and bool(_ev(n[2], ctx, informe))
    if t == "no":
        v = _ev(n[1], ctx, informe)
        return None if v is None else not v
    if t == "cmp":
        return _comparar(n[1], _ev(n[2], ctx, informe), _ev(n[3], ctx, informe), informe)
    if t == "neg":
        v = _num(_ev(n[1], ctx, informe))
        return None if v is None else -v
    if t == "bin":
        a, b = _num(_ev(n[2], ctx, informe)), _num(_ev(n[3], ctx, informe))
        if a is None or b is None:
            _anotar(informe, "operando ausente en aritmética")
            return None
        return a + b if n[1] == "+" else a - b if n[1] == "-" else a * b
    if t == "llamada":
        args = [_ev(a, ctx, informe) for a in n[2]]
        if n[1] == "largo":
            ok = len(args) == 1 and isinstance(args[0], (list, tuple, str))
            return Decimal(len(args[0])) if ok else None
        nums = [_num(a) for a in args]
        if not nums or any(x is None for x in nums):
            return None
        if n[1] == "abs":
            return abs(nums[0]) if len(nums) == 1 else None
        return min(nums) if n[1] == "min" else max(nums)
    raise ErrorCondicion(f"Nodo desconocido: {t!r}.")


def evaluar(arbol, ctx: dict, informe: list[str] | None = None) -> bool:
    """Evalúa a verdadero/falso. Cualquier fallo de tipos o dato ausente da falso."""
    try:
        return bool(_ev(arbol, ctx, informe))
    except (ErrorCondicion, InvalidOperation, ArithmeticError):
        _anotar(informe, "error de evaluación")
        return False


def evaluar_valor(arbol, ctx: dict) -> Any:
    """Valor de una expresión (p. ej. `valor_estimado_eur`); None si falta algo."""
    try:
        return _ev(arbol, ctx, None)
    except (ErrorCondicion, InvalidOperation, ArithmeticError):
        return None
