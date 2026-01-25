import sqlite3
import csv
import io
import re
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import DB_PATH
except ImportError:
    DB_PATH = "cecan.db"

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
    return name.strip().replace('  ', ' ')

def get_member_id(cursor, name):
    name = normalize_name(name)
    if not name:
        return None
    
    cursor.execute("SELECT id FROM academic_members WHERE full_name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    return None

def get_or_create_nodo(cursor, name):
    name = normalize_name(name)
    cursor.execute("SELECT id FROM nodos WHERE nombre = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO nodos (nombre) VALUES (?)", (name,))
    return cursor.lastrowid

def sync_projects():
    print(f"Starting Project Sync...")
    print(f"Database: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("ERROR: Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # WP Names Mapping
    wp_names = {
        1: "Prevención",
        2: "Optimización de trayectoria",
        3: "Innovación y medicina personalizada",
        4: "Investigación en políticas públicas",
        5: "Data para la acción"
    }

    # Ensure WPs exist with correct names
    print("Syncing WPs...")
    for wp_id, wp_name in wp_names.items():
        cursor.execute("INSERT OR IGNORE INTO wps (id, nombre) VALUES (?, ?)", (wp_id, wp_name))
        cursor.execute("UPDATE wps SET nombre = ? WHERE id = ?", (wp_name, wp_id))

    # Create member_wps table for Many-to-Many relationship
    print("Creating member_wps table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_wps (
            member_id INTEGER,
            wp_id INTEGER,
            PRIMARY KEY (member_id, wp_id),
            FOREIGN KEY(member_id) REFERENCES academic_members(id),
            FOREIGN KEY(wp_id) REFERENCES wps(id)
        )
    """)
    
    # Clear existing member_wps to ensure clean sync
    cursor.execute("DELETE FROM member_wps")

    reader = csv.DictReader(io.StringIO(RAW_DATA), delimiter='|')
    
    projects_updated = 0
    relations_created = 0
    member_wps_created = 0
    warnings = []
    
    node_headers = ['COLORECTAL', 'MAMA', 'EXPERIENCIA', 'CUELLO UTERINO', 'GASTRICO', 'VESICULA', 'PULMON', 'EPA', 'BIOMARCADORES', 'SOCIEDAD CIVIL']

    for row in reader:
        try:
            # 1. Upsert Project
            titulo = row['TITULO'].strip()
            wp_val = row['c'].strip()
            primary_wp_id = int(wp_val) if wp_val.isdigit() else None
            
            cursor.execute("SELECT id FROM proyectos WHERE titulo = ?", (titulo,))
            proj_row = cursor.fetchone()
            
            if proj_row:
                project_id = proj_row[0]
                cursor.execute("UPDATE proyectos SET wp_id = ? WHERE id = ?", (primary_wp_id, project_id))
            else:
                cursor.execute("INSERT INTO proyectos (titulo, wp_id) VALUES (?, ?)", (titulo, primary_wp_id))
                project_id = cursor.lastrowid
            
            projects_updated += 1
            
            # Identify all WPs for this row (Primary + Others)
            row_wps = set()
            if primary_wp_id:
                row_wps.add(primary_wp_id)
            
            otros_wps = row.get('otros WP involucrados')
            if otros_wps:
                ids = otros_wps.replace(' ', '').split(',')
                for wp_id_str in ids:
                    if wp_id_str.isdigit():
                        row_wps.add(int(wp_id_str))

            # 2. Sync Researchers
            # Clear existing relations for this project to ensure idempotency
            cursor.execute("DELETE FROM proyecto_investigador WHERE proyecto_id = ?", (project_id,))
            
            # Helper to add relation
            def add_relation(name, role):
                nonlocal relations_created, member_wps_created
                mid = get_member_id(cursor, name)
                if mid:
                    # Project-Researcher Relation
                    cursor.execute("INSERT INTO proyecto_investigador (proyecto_id, investigador_id, rol) VALUES (?, ?, ?)", 
                                (project_id, mid, role))
                    relations_created += 1
                    
                    # Member-WP Relations (Associate researcher with ALL WPs in this row)
                    for wp_id in row_wps:
                        cursor.execute("INSERT OR IGNORE INTO member_wps (member_id, wp_id) VALUES (?, ?)", (mid, wp_id))
                        # We can't easily count "created" with INSERT OR IGNORE without checking changes, 
                        # but we can count attempts or just ignore exact count for this metric.
                        
                else:
                    warnings.append(f"Researcher not found: {name} (Project: {titulo})")

            # Responsable
            resp_raw = row.get('Investigador responsable')
            if resp_raw:
                # Special cases
                if "Alicia Colombo, Juan Carlos Roa" in resp_raw:
                    add_relation("Alicia Colombo", "Responsable")
                    add_relation("Juan Carlos Roa", "Responsable")
                elif "Hector Contreras, Viviana Montecinos" in resp_raw:
                    add_relation("Hector Contreras", "Responsable")
                    add_relation("Viviana Montecinos", "Responsable")
                else:
                    add_relation(resp_raw, "Responsable")
            
            # Principales
            principales = row.get('Principales (8)')
            if principales:
                names = re.split(r',| y ', principales)
                for n in names:
                    if n.strip(): add_relation(n, "Principal")

            # Otros
            otros = row.get('Otros investigadores')
            if otros:
                names = re.split(r',| y ', otros)
                for n in names:
                    if n.strip(): add_relation(n, "Colaborador")
                    
            # 3. Sync Nodos (Cancer Types/Tags)
            # Clear existing nodes
            cursor.execute("DELETE FROM proyecto_nodo WHERE proyecto_id = ?", (project_id,))
            
            for header in node_headers:
                val = row.get(header)
                if val and val.strip().lower() == 'x':
                    nodo_id = get_or_create_nodo(cursor, header)
                    cursor.execute("INSERT INTO proyecto_nodo (proyecto_id, nodo_id) VALUES (?, ?)", (project_id, nodo_id))
            
            # 4. Sync Other WPs (Project-WP relation)
            cursor.execute("DELETE FROM proyecto_otrowp WHERE proyecto_id = ?", (project_id,))
            if otros_wps:
                ids = otros_wps.replace(' ', '').split(',')
                for wp_id_str in ids:
                    if wp_id_str.isdigit():
                        cursor.execute("INSERT INTO proyecto_otrowp (proyecto_id, wp_id) VALUES (?, ?)", (project_id, int(wp_id_str)))

            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"Error processing project '{titulo}': {e}")
            
    # Count total member_wps
    cursor.execute("SELECT COUNT(*) FROM member_wps")
    total_member_wps = cursor.fetchone()[0]
    
    conn.close()
    
    print("\n--- Sync Complete ---")
    print(f"Proyectos actualizados/creados: {projects_updated}")
    print(f"Relaciones Project-Researcher creadas: {relations_created}")
    print(f"Relaciones Member-WP totales: {total_member_wps}")
    
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        unique_warnings = sorted(list(set(warnings)))
        for w in unique_warnings[:10]:
            print(f" - {w}")
        if len(unique_warnings) > 10:
            print(f" ... and {len(unique_warnings)-10} more.")

if __name__ == "__main__":
    sync_projects()
