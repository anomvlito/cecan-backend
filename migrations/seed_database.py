import sqlite3
import csv
import io
import re
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from backend.config import DB_PATH
except ImportError:
    DB_PATH = "backend/cecan.db"

# He limpiado ligeramente los encabezados en el string para asegurar que se detecten bien.
# Nota: Asegúrate que entre columnas visuales haya al menos 2 espacios en el string original 
# o usa este bloque corregido:
RAW_DATA = """c|TITULO|Investigador responsable|Principales (8)|Otros investigadores|otros WP involucrados|COLORECTAL|MAMA|EXPERIENCIA|CUELLO UTERINO|GASTRICO|VESICULA|PULMON|EPA|BIOMARCADORES|SOCIEDAD CIVIL
1|Modelamiento carga evitable|Paula Margozzini|Paula Margozzini|Pedro Zitko|2,4,5|X|X||X|X|X|X||||
1|Piloto preventivo|Lorena Rodríguez|Lorena Rodríguez|María Jesús Vega, Kenny Low, Paulina Espinoza, Javiera Soto|2,4|X|X|X|X|X|X|X||||
1|Desigualdades en sobrevida|Nicolás Silva|Paula Margozzini|Felipe Medina, Tania Alfaro, Felipe Quezada, Andrea Canals, Natalia Cuadros|4|X|X||X|X|X|X||||
1|Adherencia a prevencion|Solange Parra|Lorena Rodríguez|Solange Parra, Catalina Ramírez, Carlos Celis, Carla Villagrán||X|X||X||||||
1|Toxicos ambientales|María Teresa Muñoz|Lorena Rodríguez|Katherine Marcelain, Natalia Landeros, Liliana Zúñiga|3|X|X||X|X|X|X||X|
2|Capacidades de la red|Johanna Acevedo|Johanna Acevedo|Bruno Nervi|4,5|X|X|X|X|X|X|X||||
2|Trayectoria clinica|Johanna Acevedo|Johanna Acevedo|Bruno Nervi|4,5|X|X|X|X|X|X|X||||
2|Experiencia|Karla González|Johanna Acevedo|Sofía Bowen, Valentina Garrido, Felipe Elgueta|5||||X||||||
2|Prevencion cancer gastrico|Arnoldo Riquelme|Manuel Espinoza|Klaus Puschel, Laura Huidrobro|1,3,4,5||||||X|||X|
2|Control del cancer en atencion primaria|Klaus Puschel|Johanna Acevedo|Bruno Nervi, Jose Peña, Javiera Martínez, María Gabriela Soto, Andrea Rioseco, Mauricio Soto, Carolina Goic, Francisca Menoa, Eduardo Arenas, Marcela Faúndez, Paola Lanino, Matías González|1,4,5|X|X|X|X|X|X|X||||
2|Eleccion de lugar de fallecimeinto|Pedro Pérez Cruz|Bruno Nervi|Ofelia Leiva, Javiera Léniz|1,4||X||||||||
2|Impacto EPA|Silvia Palma|Bruno Nervi|Carolina Muñoz, Francisca Márquez, Camila Lucchini, Carolina Crocquevielle, Fernanda Farías, Camila Carrasco, Natalie Pinto, Javiera Hernández|4||||X|||||x|
2|IA y deteccion cancer pulmonar|Richard Weber|Bruno Nervi|Jose Peña, Sebastián Santana, Juan Carlos Opazo, Juan Cristóbal Morales, Natalie Pinto, Nicolas Barticevic, Rodrigo Villarroel, Diego Carrillo|3||||||||x||X|
2|Optimizacion trayectoria cancer de mama|César Sánchez|Bruno Nervi|Francisco Acevedo, Johanna Acevedo|3|||x|x||||||X|
2|Neuropatia por paclitaxel y fenotipo|Francisco Acevedo|Johanna Acevedo|César Sánchez|3|||x|x||||||X|
2|Desigualdades ante cancer colorectal|Felipe Quezada|Bruno Nervi|Raúl Aguilar|4|x|||x||||||X|
3|BioBancos en red|Alicia Colombo, Juan Carlos Roa|Enrique Castellon|Gerardo Donoso, Diego Romero|2,5|x|x||x|x|x|x||X|
3|Modelos preclinicos|Hector Contreras, Viviana Montecinos|Enrique Castellon|Patricia García, Carolina Bizama, Gareth Owen, Angel Castillo|2,4|x|x||x|x|x|x||Xx|
3|Biomarcadores e inmunoterapia|Mercedes López|Enrique Castellon|Bettina Müller, Roberto Estay||x|x||x|x|x|x||||
3|Biomarcadores geneticos|Katherine Marcelain|Enrique Castellon|Ricardo Armisen, Olga Barajas, Arnaldo Marín, Giuliano Bernal|2|x|x||x|x|x|x||x|
3|MicroRNAs predictivos|Jaime González|Enrique Castellon|Héctor Contreras, Guillermo Valenzuela||x||||||||x|
3|Marco regulatorio Terapias celulares|Viviana Montecinos|Bruno Nervi|Carolina Goic, Pablo Verdugo, Juan Alberto Lecaros, Gabriela Borin|2,3||||||||||
3|Ejercicio y cancer|Karol Ramirez|Enrique Castellon|Patricia Macanás|2|x|x||||||||x|
3|IA y mamografias|Susana Mondschein|Enrique Castellon|Nicolás Silva, Arnaldo Marín|2|||x|||||||x|
3|Microbiota|Erick Riquelme|Enrique Castellon|Arnoldo Riquelme|2|x||||||x|x|||x|
3|DPYD y toxicidad por FU|Olga Barajas|Enrique Castellon|Luis Quiñones, Leslie Cerpa, Claudio Alarcón|2||||||||||x|
3|Biomarcadores e inflamacion|Carolina Ibañez|Enrique Castellon|Mauricio Cuello|2||||||||||x|
4|Sociedad civil y PNC|Báltica Cabieses|Manuel Espinoza|Alexandra Obach, Antonia Roberts, Francisca Vezzani, Carla Campaña|||||||x||||X
4|Empoderammiento sociedad civil|Báltica Cabieses|Manuel Espinoza|Alexandra Obach, Antonia Roberts, Francisca Vezzani, Carla Campaña|1,2||||||||||X
4|Uso canastas GES|Paula Bedregal|Oscar Arteaga|Carolina de la Fuente, Paula Zamorano|2||||X||||||
4|Sistema de salud ante el cancer|Paula Bedregal|Oscar Arteaga|Pedro Zitko|1||||X||||||
4|Percepcion ante sistema de salud|Paula Bedregal|Oscar Arteaga|Victoria Lermanda, Mariol Luan, Camilo Oñate||||||||X||||X
4|Calidad y atencion|Paula Bedregal|Oscar Arteaga|Matías Libuy||||||X||||X
4|Oferta oncologos|Paula Bedregal|Oscar Arteaga|Constanza Roja, Bruno Nervi|2||||X||||||X
4|Modelos de atencion|Alejandra Fuentes|Oscar Arteaga|Verónica Kramer, Carla Flores, Alondra Castillo|1,2,3|X|X|X|X|X|X|X|X||X
5|App y navegacion|Carla Taramasco|Carla Taramasco|David Araya, Orietta Nicolis, Silvia Palma, Gaston Marquez|2|X|X|X|X|X|X|X|X||X
5|Datos para la accion|Carla Taramasco|Carla Taramasco|David Araya, Orietta Nicolis, Silvia Palma, Gaston Marquez|2|X|X|X|X|X|X|X|X|X|X
5|Sobrevida y ENS|Angélica Domínguez|Carla Taramasco|Paula Margozzini|||X|X||X|X|X|X||||
2|Formacion medica|Bruno Nervi|Bruno Nervi|Enrique Castellon, Carolina Goic, Pablo Verdugo||X|X|X|X|X|X|X|X||X
2|Formacion EPA|Francisca Marquez|Bruno Nervi|Enrique Castellon, Carolina Goic, Pablo Verdugo||X|X|X|X|X|X|X|X||X
2|Tamizaje cancer pulmonar|Angello Retamales|Bruno Nervi|Carolina Velasquez, Hector Galindo, Dsiego Carrillo, Paulo Olivera|1,3,5||||||||X||X|
2|Registro cancer Vesicula Biliar|Juan Carlos Araya|Bruno Nervi|Juan Carlos Roa|5||||||X|||||
"""

def normalize_name(name):
    if not name:
        return None
    # Eliminamos espacios extra y normalizamos
    return name.strip().replace('  ', ' ')

def create_schema(cursor):
    cursor.executescript("""
        DROP TABLE IF EXISTS Proyecto_Investigador;
        DROP TABLE IF EXISTS Proyecto_Nodo;
        DROP TABLE IF EXISTS Proyecto_OtroWP;
        DROP TABLE IF EXISTS Proyectos;
        DROP TABLE IF EXISTS Investigadores;
        DROP TABLE IF EXISTS Nodos;
        DROP TABLE IF EXISTS WPs;

        CREATE TABLE WPs (
            id INTEGER PRIMARY KEY,
            nombre TEXT
        );

        CREATE TABLE Nodos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        );

        CREATE TABLE Investigadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        );

        CREATE TABLE Proyectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            wp_id INTEGER,
            FOREIGN KEY(wp_id) REFERENCES WPs(id)
        );

        CREATE TABLE Proyecto_Investigador (
            proyecto_id INTEGER,
            investigador_id INTEGER,
            rol TEXT,
            FOREIGN KEY(proyecto_id) REFERENCES Proyectos(id),
            FOREIGN KEY(investigador_id) REFERENCES Investigadores(id)
        );

        CREATE TABLE Proyecto_Nodo (
            proyecto_id INTEGER,
            nodo_id INTEGER,
            FOREIGN KEY(proyecto_id) REFERENCES Proyectos(id),
            FOREIGN KEY(nodo_id) REFERENCES Nodos(id)
        );
        
        CREATE TABLE Proyecto_OtroWP (
            proyecto_id INTEGER,
            wp_id INTEGER,
            FOREIGN KEY(proyecto_id) REFERENCES Proyectos(id),
            FOREIGN KEY(wp_id) REFERENCES WPs(id)
        );
    """)

    wps = [
        (1, 'Prevención'),
        (2, 'Optimización de trayectoria'),
        (3, 'Innovación y medicina personalizada'),
        (4, 'Investigación en políticas públicas'),
        (5, 'Data para la acción')
    ]
    cursor.executemany("INSERT INTO WPs (id, nombre) VALUES (?, ?)", wps)

def get_or_create_investigator(cursor, name):
    name = normalize_name(name)
    if not name:
        return None
    
    cursor.execute("SELECT id FROM Investigadores WHERE nombre = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    cursor.execute("INSERT INTO Investigadores (nombre) VALUES (?)", (name,))
    return cursor.lastrowid

def get_or_create_nodo(cursor, name):
    name = normalize_name(name)
    cursor.execute("SELECT id FROM Nodos WHERE nombre = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO Nodos (nombre) VALUES (?)", (name,))
    return cursor.lastrowid

def process_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    create_schema(cursor)
    
    # --- CORRECCIÓN IMPORTANTE ---
    # Usamos el RAW_DATA pre-procesado con pipes '|' para evitar ambigüedad con los espacios
    reader = csv.DictReader(io.StringIO(RAW_DATA), delimiter='|')
    
    node_headers = ['COLORECTAL', 'MAMA', 'EXPERIENCIA', 'CUELLO UTERINO', 'GASTRICO', 'VESICULA', 'PULMON', 'EPA', 'BIOMARCADORES', 'SOCIEDAD CIVIL']

    for row in reader:
        try:
            # Usamos .strip() porque a veces quedan espacios invisibles
            wp_val = row['c'].strip()
            if not wp_val: continue 
            wp_id = int(wp_val)
        except (ValueError, KeyError) as e:
            print(f"Error saltando fila: {e} en fila: {row}")
            continue 
            
        titulo = row['TITULO'].strip()
        
        cursor.execute("INSERT INTO Proyectos (titulo, wp_id) VALUES (?, ?)", (titulo, wp_id))
        project_id = cursor.lastrowid
        
        # Procesar Investigadores
        resp_name = row.get('Investigador responsable')
        if resp_name:
            inv_id = get_or_create_investigator(cursor, resp_name)
            if inv_id: # Check extra de seguridad
                cursor.execute("INSERT INTO Proyecto_Investigador (proyecto_id, investigador_id, rol) VALUES (?, ?, ?)", 
                           (project_id, inv_id, 'Responsable'))
            
        # Principales
        principales = row.get('Principales (8)')
        if principales:
            # Mejoramos el split para soportar ' y ' y ','
            names = re.split(r',| y ', principales)
            for name in names:
                inv_id = get_or_create_investigator(cursor, name)
                if inv_id:
                    cursor.execute("INSERT INTO Proyecto_Investigador (proyecto_id, investigador_id, rol) VALUES (?, ?, ?)", 
                                (project_id, inv_id, 'Principal'))

        # Otros
        otros = row.get('Otros investigadores')
        if otros:
            names = re.split(r',| y ', otros)
            for name in names:
                inv_id = get_or_create_investigator(cursor, name)
                if inv_id:
                    cursor.execute("INSERT INTO Proyecto_Investigador (proyecto_id, investigador_id, rol) VALUES (?, ?, ?)", 
                                (project_id, inv_id, 'Colaborador'))
                                
        # Nodos
        for header in node_headers:
            val = row.get(header)
            if val and val.strip().lower() == 'x':
                nodo_id = get_or_create_nodo(cursor, header)
                cursor.execute("INSERT INTO Proyecto_Nodo (proyecto_id, nodo_id) VALUES (?, ?)", (project_id, nodo_id))
                
        # Otros WPs
        otros_wps = row.get('otros WP involucrados')
        if otros_wps:
            ids = otros_wps.replace(' ', '').split(',')
            for wp_id_str in ids:
                if wp_id_str.isdigit():
                    cursor.execute("INSERT INTO Proyecto_OtroWP (proyecto_id, wp_id) VALUES (?, ?)", (project_id, int(wp_id_str)))

    conn.commit()
    
    print("Base de datos creada exitosamente.")
    cursor.execute("SELECT COUNT(*) FROM Proyectos")
    print(f"Proyectos: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM Investigadores")
    print(f"Investigadores: {cursor.fetchone()[0]}")
    
    conn.close()

if __name__ == "__main__":
    process_data()
