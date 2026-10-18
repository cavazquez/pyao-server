# Libro persistido y entrega inicial (#135)

El login lee exactamente los slots persistidos, incluidos huecos y orden. Agregar
un hechizo al catálogo no enseña nada. Los libros antiguos se conservan sin
migración destructiva: un perfil existente sin libro sigue sin libro y puede
aprender mediante pergaminos. No se convierten cuentas existentes en cuentas nuevas.

Al crear el personaje se entrega una sola vez `game.spells.starter_by_class`.
La distribución configura Dardo Mágico (2) y Curar Heridas Leves (3) para las
12 clases; la tabla puede dar un conjunto distinto o vacío por clase. Libro y
marca `spellbook_seeded` se confirman juntos mediante WATCH/MULTI. Ni reintentar
la inicialización ni vaciar un libro ya inicializado regenera hechizos.

`game.spells.development_all_spells=false` es el valor de distribución. Sólo
habilitar explícitamente ese modo permite rellenar todo el catálogo durante login.
Los 35 slots del libro y los 30 del inventario permanecen iguales.

La barca inicial se entrega al crear el inventario, junto con las herramientas;
`send_inventory` ya no modifica recursos. Una cuenta antigua sin barca debe
conseguirla dentro del juego. No se vuelve a entregar por venderla o dropearla.
