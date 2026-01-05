
import io
import csv
import re
import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# Add project root to path
sys.path.append(os.getcwd())

from core.models import (
    Base, WorkPackage, Project, ProjectResearcher, Node, ProjectNode, 
    ProjectOtherWP, AcademicMember, MemberType, Student, Thesis
)
from config import SQLALCHEMY_DATABASE_URL

# RAW DATA (Unchanged content, just logic needed)
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

def get_or_create_investigator(session, name):
    name = normalize_name(name)
    if not name:
        return None
    
    # Check if exists (assuming full_name is unique or close enough for seed)
    member = session.query(AcademicMember).filter(AcademicMember.full_name == name).first()
    if member:
        return member
    
    # Create new
    member = AcademicMember(
        full_name=name,
        member_type=MemberType.RESEARCHER,
        institution="CECAN (Unknown)", # Placeholder
        email=f"{name.lower().replace(' ', '.')}@example.com" # Placeholder email
    )
    session.add(member)
    session.commit()
    return member

def get_or_create_node(session, name):
    name = normalize_name(name)
    node = session.query(Node).filter(Node.name == name).first()
    if node:
        return node
    
    node = Node(name=name)
    session.add(node)
    session.commit()
    return node

def seed_database():
    print(f"🌱 Seeding database via {SQLALCHEMY_DATABASE_URL}")
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    # DROP OLD SPANGLISH TABLES (Force Cleanup of Zombie Tables)
    # These tables exist in the DB but are no longer in our Base.metadata models, 
    # so drop_all() ignores them, causing FK constraints to block other drops.
    old_tables = [
        "investigador_publicacion",
        "proyecto_investigador",
        "proyecto_nodo",
        "proyecto_otrowp",
        "proyectos",
        "nodos",
        "wps",
        "academic_members", # Force drop this too as it is a common dependency
        "publications",
    ]
    
    print("⚠️  Forcefully dropping old tables (CASCADE)...")
    with engine.connect() as conn:
        from sqlalchemy import text
        for table in old_tables:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                print(f"   - Dropped {table}")
            except Exception as e:
                print(f"   - Could not drop {table}: {e}")
        conn.commit()
    
    # NOW standard drop and create
    print("⚠️  Dropping any remaining tables...")
    Base.metadata.drop_all(bind=engine)
    print("✨ Creating all tables...")
    Base.metadata.create_all(bind=engine)
    
    session = Session(bind=engine)
    
    # 1. Seed Work Packages
    print("📦 Seeding Work Packages...")
    wps_data = [
        (1, 'Prevención'),
        (2, 'Optimización de trayectoria'),
        (3, 'Innovación y medicina personalizada'),
        (4, 'Investigación en políticas públicas'),
        (5, 'Data para la acción')
    ]
    for wp_id, wp_name in wps_data:
        wp = WorkPackage(id=wp_id, name=wp_name)
        session.add(wp)
    session.commit()
    
    # 2. Process CSV Data
    print("📄 Processing Project Data...")
    reader = csv.DictReader(io.StringIO(RAW_DATA), delimiter='|')
    node_headers = ['COLORECTAL', 'MAMA', 'EXPERIENCIA', 'CUELLO UTERINO', 'GASTRICO', 'VESICULA', 'PULMON', 'EPA', 'BIOMARCADORES', 'SOCIEDAD CIVIL']

    for row in reader:
        try:
            wp_val = row.get('c', '').strip()
            if not wp_val: continue
            wp_id = int(wp_val)
        except (ValueError, KeyError):
            continue
            
        titulo = row.get('TITULO', '').strip()
        
        # Create Project
        project = Project(title=titulo, wp_id=wp_id)
        session.add(project)
        session.commit()
        
        # Researchers
        resp_name = row.get('Investigador responsable')
        if resp_name:
            inv = get_or_create_investigator(session, resp_name)
            if inv:
                # Add relation
                rel = ProjectResearcher(project_id=project.id, member_id=inv.id, role='Responsable')
                session.add(rel)
                
        # Principales
        principales = row.get('Principales (8)')
        if principales:
            names = re.split(r',| y ', principales)
            for name in names:
                inv = get_or_create_investigator(session, name)
                if inv:
                    rel = ProjectResearcher(project_id=project.id, member_id=inv.id, role='Principal')
                    session.add(rel)
        
        # Otros
        otros = row.get('Otros investigadores')
        if otros:
            names = re.split(r',| y ', otros)
            for name in names:
                inv = get_or_create_investigator(session, name)
                if inv:
                    rel = ProjectResearcher(project_id=project.id, member_id=inv.id, role='Colaborador')
                    session.add(rel)

        # Nodes
        for header in node_headers:
            val = row.get(header)
            if val and val.strip().lower() == 'x':
                node = get_or_create_node(session, header)
                rel = ProjectNode(project_id=project.id, node_id=node.id)
                session.add(rel)
                
        # Other WPs
        otros_wps = row.get('otros WP involucrados')
        if otros_wps:
            ids = outros_wps = otros_wps.replace(' ', '').split(',')
            for wp_id_str in ids:
                if wp_id_str.isdigit():
                    rel = ProjectOtherWP(project_id=project.id, wp_id=int(wp_id_str))
                    session.add(rel)
        session.commit()

    print("✅ Database Seeded Successfully!")
    count_projects = session.query(Project).count()
    count_members = session.query(AcademicMember).count()
    print(f"📊 Stats: {count_projects} Projects, {count_members} Researchers")
    session.close()

if __name__ == "__main__":
    seed_database()
