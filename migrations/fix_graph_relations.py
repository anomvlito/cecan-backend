import sqlite3
import csv
import io
import re
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH

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
3|Sociedad civil y PNC|Báltica Cabieses|Manuel Espinoza|Alexandra Obach, Antonia Roberts, Francisca Vezzani, Carla Campaña|||||||x||||X
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
    return name.strip().replace('  ', ' ')

def get_member_id(cursor, name):
    name = normalize_name(name)
    if not name:
        return None
    
    # Try exact match
    cursor.execute("SELECT id FROM academic_members WHERE full_name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
        
    # Try partial match if needed (optional, but safer to stick to exact for now)
    return None

def fix_relations():
    print(f"Starting graph relations fix...")
    print(f"Using database at: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Debug: List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Tables in DB: {tables}")
    
    if 'proyectos' not in tables and 'Proyectos' not in tables:
        print("CRITICAL ERROR: 'proyectos' table not found!")
    
    # Re-create table to ensure schema is correct
    print("Re-creating table proyecto_investigador...")
    cursor.execute("DROP TABLE IF EXISTS proyecto_investigador")
    cursor.execute("DROP TABLE IF EXISTS Proyecto_Investigador") # Drop legacy mixed-case if exists
    
    cursor.execute("""
        CREATE TABLE proyecto_investigador (
            proyecto_id INTEGER,
            investigador_id INTEGER,
            rol TEXT,
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id),
            FOREIGN KEY(investigador_id) REFERENCES academic_members(id)
        )
    """)
    
    reader = csv.DictReader(io.StringIO(RAW_DATA), delimiter='|')
    
    count = 0
    errors = 0
    
    for row in reader:
        titulo = row['TITULO'].strip()
        
        # Get Project ID
        cursor.execute("SELECT id FROM proyectos WHERE titulo = ?", (titulo,))
        proj_row = cursor.fetchone()
        
        if not proj_row:
            print(f"Warning: Project not found: {titulo}")
            continue
            
        project_id = proj_row[0]
        
        # 1. Responsable
        resp_name = row.get('Investigador responsable')
        if resp_name:
            member_id = get_member_id(cursor, resp_name)
            if member_id:
                cursor.execute("INSERT INTO proyecto_investigador (proyecto_id, investigador_id, rol) VALUES (?, ?, ?)", 
                           (project_id, member_id, 'Responsable'))
                count += 1
            else:
                print(f"Member not found: {resp_name}")
                errors += 1

        # 2. Principales
        principales = row.get('Principales (8)')
        if principales:
            names = re.split(r',| y ', principales)
            for name in names:
                member_id = get_member_id(cursor, name)
                if member_id:
                    cursor.execute("INSERT INTO proyecto_investigador (proyecto_id, investigador_id, rol) VALUES (?, ?, ?)", 
                                (project_id, member_id, 'Principal'))
                    count += 1
                else:
                     if name.strip():
                        print(f"Member not found: {name}")
                        errors += 1

        # 3. Otros
        otros = row.get('Otros investigadores')
        if otros:
            names = re.split(r',| y ', otros)
            for name in names:
                member_id = get_member_id(cursor, name)
                if member_id:
                    cursor.execute("INSERT INTO proyecto_investigador (proyecto_id, investigador_id, rol) VALUES (?, ?, ?)", 
                                (project_id, member_id, 'Colaborador'))
                    count += 1
                else:
                    if name.strip():
                        print(f"Member not found: {name}")
                        errors += 1

    conn.commit()
    conn.close()
    print(f"\nFix complete.")
    print(f"Restored {count} relationships.")
    print(f"Errors (members not found): {errors}")

if __name__ == "__main__":
    fix_relations()
