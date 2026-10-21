# Accesorios del catálogo

ObjType 18 contiene cuatro anillos, seis instrumentos mágicos y dos guantes. Todos usan una única ranura `accessory` referida al slot de inventario; reemplazar o desequipar no suma modificadores persistentes. Las restricciones `ClasesProhibidas` se comprueban sobre el personaje vivo en el mismo snapshot que inventario y equipo.

Los cuatro anillos usan `DefensaMagicaMin/Max`: cada daño mágico directo o de área contra el jugador resta la media entera de ese rango antes de la barrera, con mínimo cero. La interfaz recibe el rango de resistencia del catálogo. No aporta defensa física.

Los instrumentos con `StaffPower > 0` satisfacen el requisito de foco/bastón de los hechizos que lo exigen. No se inventa un multiplicador de daño. Los dos instrumentos Newbie no declaran StaffPower: se pueden equipar, pero no se les concede un poder inexistente en los datos.

Los guantes usan sus `MinHit/MaxHit` al combatir sin arma, manteniendo la habilidad de lucha; al sostener un arma se usa el arma y el guante no duplica ese daño. Su efecto se deriva del equipo observado al atacar, sin alterar los atributos guardados.

Ninguno de estos accesorios declara una capa gráfica para el avatar. La marca de equipado en inventario es la presentación correspondiente. Las botas siguen aplazadas por decisión del usuario: cliente #181 y parte pendiente de #179.
