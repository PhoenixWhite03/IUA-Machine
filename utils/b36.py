# © 2026 David Ali Caballero Pérez. All rights reserved.
class Base36:
    ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, value):
        if isinstance(value, str):
            self.value = int(value, 36)
        elif isinstance(value, int):
            self.value = value
        elif isinstance(value, Base36):
            self.value = value.value
        else:
            raise TypeError("El valor debe ser int, str o Base36")

    def _to_base36(self, n):
        if n == 0:
            return "0"
        sign = "-" if n < 0 else ""
        n = abs(n)
        res = ""
        while n > 0:
            n, rem = divmod(n, 36)
            res = self.ALPHABET[rem] + res
        return sign + res

    def __str__(self):
        return self._to_base36(self.value)

    def __repr__(self):
        return f"Base36('{self._to_base36(self.value)}')"

    def __add__(self, other):
        if isinstance(other, (int, Base36)):
            other_val = other.value if isinstance(other, Base36) else other
            return Base36(self.value + other_val)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, (int, Base36)):
            other_val = other.value if isinstance(other, Base36) else other
            return Base36(self.value - other_val)
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, (int, Base36)):
            other_val = other.value if isinstance(other, Base36) else other
            return self.value == other_val
        return False

    def __mul__(self, other):
        """Define el comportamiento de la multiplicación (*)"""
        if isinstance(other, (int, Base36)):
            other_val = other.value if isinstance(other, Base36) else other
            return Base36(self.value * other_val)
        return NotImplemented

    def __truediv__(self, other):
        """Define el comportamiento de la división real (/)"""
        if isinstance(other, (int, Base36)):
            other_val = other.value if isinstance(other, Base36) else other
            # En Python, la división real (/) entre enteros devuelve un float.
            # Por lo tanto, retornamos un float en lugar de un Base36.
            return self.value / other_val
        return NotImplemented

    def __floordiv__(self, other):
        """Define la división entera (//). Opcional, pero muy recomendada para devolver Base36"""
        if isinstance(other, (int, Base36)):
            other_val = other.value if isinstance(other, Base36) else other
            return Base36(self.value // other_val)
        return NotImplemented

    def __lt__(self, other):
        """Define si es menor que (<), permitiendo ordenar listas con sort()"""
        if isinstance(other, (int, Base36)):
            other_val = other.value if isinstance(other, Base36) else other
            return self.value < other_val
        return NotImplemented

    def __int__(self):
        """Permite la conversión directa usando int(objeto)"""
        return self.value

    def __format__(self, format_spec):
        """
        Define cómo interactúa el objeto con los f-strings o format().
        Se delega el formateo a la representación en cadena de texto del Base36.
        """
        base36_str = str(self)
        # Aplicamos las reglas nativas de formato de strings en Python
        return format(base36_str, format_spec)
