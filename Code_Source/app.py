from flask import Flask, render_template, request, redirect, url_for, flash,session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from pymongo import MongoClient
from flask_session import Session
from neo4j import GraphDatabase
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash

# Connexion à MongoDB
mongo_client = MongoClient('localhost', 27017)
db = mongo_client['bibliotheque']
prets_collection = db['prets1']
users_collection = db['users']
  # Collection pour les utilisateurs

# Connexion à Neo4j
driver = GraphDatabase.driver('bolt://localhost:7687', auth=("neo4j", ""))

app = Flask(__name__)
app.secret_key = 'abc'  # Définir la secret_key
app.config['SECRET_KEY'] = 'abc'
app.config['SESSION_TYPE'] = 'filesystem'

Session(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Page de connexion

class User(UserMixin):
    def __init__(self, username, password, role):
        self.username = username
        self.password_hash = password
        self.role = role
       

    def get_id(self):
        return self.username

@login_manager.user_loader
def load_user(username):
    user_data = users_collection.find_one({"username": username})
    if user_data:
        return User(user_data['username'], user_data['password'], user_data['role'])
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash("Vous n'avez pas la permission d'accéder à cette page.")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes pour l'authentification
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        session['username'] = username
        user_data = users_collection.find_one({"username": username})
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data['username'], user_data['password'], user_data['role'])
            login_user(user)
            return redirect(url_for('index'))
        flash('Nom d\'utilisateur ou mot de passe incorrect.')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Vérifier si l'utilisateur existe déjà
        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            flash("Nom d'utilisateur déjà pris.")
            return redirect(url_for('signup'))
        
        # Hacher le mot de passe
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        # Ajouter le nouvel utilisateur avec le rôle "user"
        new_user = {
            "username": username,
            "password": hashed_password,
            "role": "user"  # Par défaut, tous les nouveaux utilisateurs sont des utilisateurs ordinaires
        }
        users_collection.insert_one(new_user)
        
        flash("Inscription réussie. Vous pouvez maintenant vous connecter.")
        return redirect(url_for('login'))
    
    return render_template('signup.html')
# =============================================================================
# def signup():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         role = request.form['role']  # 'admin' ou 'user'
#         password_hash = generate_password_hash(password)
#         users_collection.insert_one({"username": username, "password": password_hash, "role": role})
#         flash('Utilisateur enregistré avec succès.')
#         return redirect(url_for('login'))
#     return render_template('signup.html')
# =============================================================================

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Route protégée par authentification
@app.route('/')
def index():
    return render_template('index.html')

# Ajoutez les décorateurs login_required et admin_required aux routes nécessitant une authentification
@app.route('/ajouter_livre', methods=['GET', 'POST'])
@login_required
def ajouter_livre():
    if request.method == 'POST':
        titre = request.form.get('titre').strip()
        auteur = request.form.get('auteur').strip()
        genres = request.form.getlist('genre')
        resume = request.form.get('resume').strip()
        max_emprunts = int(request.form.get('max_emprunts', 1))
        quantite_disponible = int(request.form.get('quantite_disponible', 1))
        
        # Validation et ajout du livre dans la base de données
        if not titre or not auteur or not genres:
            flash("Titre, Auteur et Genre sont obligatoires", "error")
        else:
            genres_str = ', '.join(genres)
            with driver.session() as session:
                session.run("""
                    CREATE (livre:Livre {titre: $titre, genres: $genres, resume: $resume, max_emprunts: $max_emprunts, quantite_disponible: $quantite_disponible})
                    MERGE (auteur:Auteur {nom: $auteur})
                    MERGE (livre)<-[:A_ECRIT]-(auteur)
                """, {
                    'titre': titre,
                    'auteur': auteur,
                    'genres': genres_str,
                    'resume': resume,
                    'max_emprunts': max_emprunts,
                    'quantite_disponible': quantite_disponible
                })
            flash("Livre ajouté avec succès", "success")
            return redirect(url_for('liste_livres'))
    
    return render_template('ajouter_livre.html')


# =============================================================================
# def ajouter_livre():
#     if request.method == 'POST':
#         titre = request.form['titre']
#         auteur = request.form['auteur']
#         genre = request.form.get('genre')
#         resume = request.form.get('resume')
#         max_emprunts = int(request.form.get('max_emprunts', 1))  # Ajout de max_emprunts avec une valeur par défaut de 1
#         with driver.session() as session:
#             result = session.run("MATCH (a:Auteur {nom: $auteur}) RETURN a", auteur=auteur)
#             auteur_node = result.single()
#             if not auteur_node:
#                 session.run("CREATE (a:Auteur {nom: $auteur})", auteur=auteur)
#             session.run("MATCH (a:Auteur {nom: $auteur}) "
#                         "CREATE (l:Livre {titre: $titre, genre: $genre, resume: $resume, max_emprunts: $max_emprunts}) "
#                         "CREATE (a)-[:A_ECRIT]->(l)",
#                         auteur=auteur, titre=titre, genre=genre, resume=resume, max_emprunts=max_emprunts)
#         return redirect(url_for('index'))
#     return render_template('ajouter_livre.html')
# 
# =============================================================================


@app.route('/liste_livres', methods=['GET', 'POST'])
@login_required
def liste_livres():
    if request.method == 'POST':
        # Récupère la valeur du champ de recherche
        recherche = request.form.get('recherche', '').strip().lower()
        
        # Construit la requête Cypher dynamiquement en fonction du critère de recherche
        query = """
        MATCH (livre:Livre)<-[:A_ECRIT]-(a:Auteur)
        WHERE toLower(livre.titre) CONTAINS $recherche OR toLower(a.nom) CONTAINS $recherche
        RETURN livre, a
        """
        params = {'recherche': recherche}
        
    else:
        # Requête par défaut pour récupérer tous les livres et leurs auteurs
        query = "MATCH (livre:Livre)<-[:A_ECRIT]-(a:Auteur) RETURN livre, a"
        params = {}

    # Exécute la requête Cypher avec les paramètres
    with driver.session() as session:
        result = session.run(query, params)
        livres = []
        for record in result:
            livre = record['livre']
            auteur = record['a']
            genres_str = livre.get('genres', 'N/A')
            genres = genres_str if genres_str != 'N/A' else ''
            # Ajoute les informations sur chaque livre à la liste
            livres.append({
                'titre': livre['titre'],
                'auteur': auteur['nom'],
                'genre': genres,
                'resume': livre.get('resume', 'N/A'),
                'quantite_disponible': livre.get('quantite_disponible', 0)  # Ajouter la quantité disponible
            })
    
    # Rend le template avec la liste des livres
    return render_template('liste_livres.html', livres=livres)

# =============================================================================
# def liste_livres():
#     if request.method == 'POST':
#         recherche_titre = request.form['recherche_titre']
#         query = "MATCH (livre:Livre)<-[:A_ECRIT]-(a:Auteur) WHERE livre.titre CONTAINS $recherche_titre RETURN livre, a"
#         params = {'recherche_titre': recherche_titre}
#     else:
#         query = "MATCH (livre:Livre)<-[:A_ECRIT]-(a:Auteur) RETURN livre, a"
#         params = {}
# 
#     with driver.session() as session:
#         result = session.run(query, params)
#         livres = []
#         for record in result:
#             livre = record['livre']
#             auteur = record['a']
#             livres.append({
#                 'titre': livre['titre'],
#                 'auteur': auteur['nom'],
#                 'genre': livre.get('genre', 'N/A'),
#                 'resume': livre.get('resume', 'N/A'),
#                 'quantite_disponible': livre.get('quantite_disponible', 0)  # Ajouter la quantité disponible
#             })
#     return render_template('liste_livres.html', livres=livres)
# =============================================================================

# =============================================================================
# def liste_livres():
#     if request.method == 'POST':
#         recherche_titre = request.form['recherche_titre']
#         query = "MATCH (livre:Livre)<-[:A_ECRIT]-(a:Auteur) WHERE livre.titre CONTAINS $recherche_titre RETURN livre, a"
#         params = {'recherche_titre': recherche_titre}
#     else:
#         query = "MATCH (livre:Livre)<-[:A_ECRIT]-(a:Auteur) RETURN livre, a"
#         params = {}
#     
#     with driver.session() as session:
#         result = session.run(query, params)
#         livres = []
#         for record in result:
#             livre = record['livre']
#             auteur = record['a']
#             livres.append({
#                 'titre': livre['titre'],
#                 'auteur': auteur['nom'],
#                 'genre': livre.get('genre', 'N/A'),
#                 'resume': livre.get('resume', 'N/A')
#             })
#     return render_template('liste_livres.html', livres=livres)
# =============================================================================

@app.route('/modifier_livre/<titre>', methods=['GET', 'POST'])
@login_required
@admin_required
def modifier_livre(titre):
    if request.method == 'POST':
        nouveau_titre = request.form.get('nouveau_titre')
        nouveau_genres = request.form.getlist('nouveau_genre')
        nouveau_resume = request.form.get('nouveau_resume')
        nouvelle_quantite = int(request.form.get('nouvelle_quantite', 0))
        genres_str = ', '.join(nouveau_genres)
        
        with driver.session() as session:
            # Requête pour ajouter les nouveaux genres à ceux existants
            session.run("""
                MATCH (livre:Livre {titre: $titre})
                SET livre.titre = COALESCE($nouveau_titre, livre.titre),
                    livre.genres = COALESCE($nouveau_genre, livre.genres),
                    livre.resume = COALESCE($nouveau_resume, livre.resume),
                    livre.quantite_disponible = $nouvelle_quantite
            """, titre=titre, nouveau_titre=nouveau_titre, nouveau_genre=genres_str, 
                nouveau_resume=nouveau_resume, nouvelle_quantite=nouvelle_quantite)
        print (genres_str)
        return redirect(url_for('liste_livres'))
    else:
        with driver.session() as session:
            result = session.run("MATCH (livre:Livre {titre: $titre}) RETURN livre", titre=titre)
            livre = result.single()['livre']
            return render_template('modifier_livre.html', titre=titre, livre=livre)


# =============================================================================
# def modifier_livre(titre):
#     if request.method == 'POST':
#         nouveau_titre = request.form.get('nouveau_titre')
#         nouveau_genre = request.form.get('nouveau_genre')
#         nouveau_resume = request.form.get('nouveau_resume')
#         with driver.session() as session:
#             session.run("MATCH (livre:Livre {titre: $titre}) "
#                         "SET livre.titre = COALESCE($nouveau_titre, livre.titre), "
#                         "livre.genre = COALESCE($nouveau_genre, livre.genre), "
#                         "livre.resume = COALESCE($nouveau_resume, livre.resume)",
#                         titre=titre, nouveau_titre=nouveau_titre, nouveau_genre=nouveau_genre, nouveau_resume=nouveau_resume)
#         return redirect(url_for('liste_livres'))
#     return render_template('modifier_livre.html', titre=titre)
# =============================================================================

@app.route('/supprimer_livre/<titre>', methods=['POST'])
@login_required
@admin_required
def supprimer_livre(titre):
     with driver.session() as session:
         session.run("MATCH (livre:Livre {titre: $titre}) DETACH DELETE livre", titre=titre)
     flash('Livre supprimé avec succès.')
     return redirect(url_for('liste_livres'))



@app.route('/emprunter_livre', methods=['GET', 'POST'])
def emprunter_livre():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash("Veuillez vous connecter pour emprunter un livre.")
            return redirect(url_for('login'))

        livre_titre = request.form.get('livre_titre')

        if not livre_titre:
            flash("Veuillez saisir un titre de livre.")
            return redirect(url_for('emprunter_livre'))

        with driver.session() as session_neo:
            livre = session_neo.run("MATCH (livre:Livre {titre: $titre}) RETURN livre", titre=livre_titre).single()
            if not livre:
                flash("Livre non trouvé.")
                return redirect(url_for('emprunter_livre',error="Livre non trouvé."))
            
            livre = livre['livre']
            
            quantite_disponible = livre.get('quantite_disponible', 0)
            if quantite_disponible <= 0:
                flash("Le livre n'est pas disponible.")
                return redirect(url_for('emprunter_livre', error="Le livre n'est pas disponible."))

            emprunts_actifs = prets_collection.count_documents({"livre_titre": livre_titre, "date_retour": None})
            if emprunts_actifs >= livre.get("max_emprunts", 1):
                flash("Le nombre maximum d'emprunts pour ce livre est atteint.")
                return redirect(url_for('emprunter_livre', error="Le nombre maximum d'emprunts pour ce livre est atteint."))
            
            # Décrémenter la quantité disponible
            session_neo.run(
                "MATCH (l:Livre {titre: $titre}) "
                "SET l.quantite_disponible = l.quantite_disponible - 1",
                titre=livre_titre
            )

            # Enregistrer l'emprunt
            emprunt = {
                "username": current_user.username,
                "livre_titre": livre_titre,
                "date_emprunt": datetime.now(),
                "date_retour": None
            }
            prets_collection.insert_one(emprunt)
            flash("Livre emprunté avec succès.")
        return redirect(url_for('index'))
    
    return render_template('emprunter_livre.html', error=request.args.get('error'))

# =============================================================================
# def emprunter_livre():
#     if request.method == 'POST':
#         if not current_user.is_authenticated:
#             flash("Veuillez vous connecter pour emprunter un livre.")
#             return redirect(url_for('login'))
# 
#         livre_titre = request.form.get('livre_titre')
# 
#         if not livre_titre:
#             flash("Veuillez saisir un titre de livre.")
#             return redirect(url_for('emprunter_livre'))
# 
#         with driver.session() as session_neo:
#             livre = session_neo.run("MATCH (livre:Livre {titre: $titre}) RETURN livre", titre=livre_titre).single()
#             if not livre:
#                 flash("Livre non trouvé.")
#                 return redirect(url_for('emprunter_livre'))
#             
#             livre = livre['livre']
#             
#             emprunts_actifs = prets_collection.count_documents({"livre_titre": livre_titre, "date_retour": None})
#             if emprunts_actifs >= livre.get("max_emprunts", 1):
#                 flash("Le nombre maximum d'emprunts pour ce livre est atteint.")
#                 return redirect(url_for('emprunter_livre'))
#             
#             emprunt = {
#                 "username": current_user.username,
#                 "livre_titre": livre_titre,
#                 "date_emprunt": datetime.now(),
#                 "date_retour": None
#             }
#             prets_collection.insert_one(emprunt)
#             flash("Livre emprunté avec succès.")
#         return redirect(url_for('index'))
#     
#     return render_template('emprunter_livre.html')
# =============================================================================


@app.route('/retourner_livre', methods=['GET', 'POST'])
@login_required
@admin_required
def retourner_livre():
    if request.method == 'POST':
        username = request.form['username']
        livre_titre = request.form['livre_titre']
        
        # Vérification que l'utilisateur existe
        adherent = users_collection.find_one({"username": username})
        if not adherent:
            flash("Adhérent non trouvé.")
            return redirect(url_for('retourner_livre'))
        
        # Recherche du prêt actif
        pret = prets_collection.find_one({"username": username, "livre_titre": livre_titre, "date_retour": None})
        if not pret:
            flash("Aucun emprunt actif trouvé pour ce livre.")
            return redirect(url_for('retourner_livre'))
        
        # Mettre à jour la date de retour du prêt (cette étape reste inchangée)
        prets_collection.update_one(
            {"_id": pret["_id"]},
            {"$set": {"date_retour": datetime.now()}}
        )
        
        # Trouver le livre et incrémenter la quantité disponible (utilisation de Neo4j)
        with driver.session() as session:
            result = session.run("MATCH (l:Livre {titre: $titre}) SET l.quantite_disponible = l.quantite_disponible + 1", titre=livre_titre)
        
        flash("Livre retourné avec succès.")
        return redirect(url_for('index'))
    
    return render_template('retourner_livre.html')

# =============================================================================
# def retourner_livre():
#     if request.method == 'POST':
#         username = request.form['username']
#         livre_titre = request.form['livre_titre']
#         
#         # Vérification que l'utilisateur existe
#         adherent = users_collection.find_one({"username": username})
#         if not adherent:
#             flash("Adhérent non trouvé.")
#             return redirect(url_for('retourner_livre'))
#         
#         # Recherche du prêt actif
#         pret = prets_collection.find_one({"username": username, "livre_titre": livre_titre, "date_retour": None})
#         if not pret:
#             flash("Aucun emprunt actif trouvé pour ce livre.")
#             return redirect(url_for('retourner_livre'))
#         
#         # Enregistrement de la date de retour
#         prets_collection.update_one(
#             {"_id": pret["_id"]},
#             {"$set": {"date_retour": datetime.now()}}
#         )
#         flash("Livre retourné avec succès.")
#         return redirect(url_for('index'))
#     
#     return render_template('retourner_livre.html')
# =============================================================================


@app.route('/historique_prets/')
def historique_prets():
    if 'username' not in session:
        return "Utilisateur non authentifié", 401

    search_username = request.args.get('username', '')
    
    if current_user.role == 'admin':
        # Si l'utilisateur est un administrateur, permettre la recherche de l'historique des prêts de tous les utilisateurs
        if search_username:
            prets = prets_collection.find({"username": {"$regex": search_username, "$options": "i"}})
        else:
            prets = prets_collection.find()
    else:
        # Si l'utilisateur n'est pas un administrateur, afficher uniquement son propre historique de prêts
        prets = prets_collection.find({"username": session["username"]})

    return render_template('historique_prets.html', prets=prets)

# =============================================================================
# def historique_prets():
#     if 'username' not in session:
#         return "Utilisateur non authentifié", 401
#     if current_user.role == 'admin':
#         # Si l'utilisateur est un administrateur, récupérer l'historique des prêts de tous les utilisateurs
#         prets = prets_collection.find()
#     else:
#          username = session["username"]
#          prets = prets_collection.find({"username": username})
# =============================================================================
         
   
    return render_template('historique_prets.html', prets=prets)
@app.route('/liste_adherents')
@login_required
@admin_required
def liste_adherents():
    adherents = users_collection.find()
    return render_template('liste_adherents.html', adherents=adherents)



# Route pour supprimer un adhérent


@app.route('/supprimer_adherent/<username>', methods=['GET', 'POST'])
@login_required
@admin_required
def supprimer_adherent(username):
    users_collection.delete_one({"username": username})
    return redirect(url_for('liste_adherents'))

# Route pour modifier un adhérent
@app.route('/modifier_adherent/<username>', methods=['GET', 'POST'])
@login_required
@admin_required
def modifier_adherent(username):
    adherent = users_collection.find_one({"username": username})
    
    if request.method == 'POST':
        nouveau_nom = request.form.get('username')
        nouveau_role = request.form.get('nouveau_role')
        nouveau_mot_de_passe = request.form.get('nouveau_mot_de_passe')
        
        # Vérification si un nouveau mot de passe est fourni
        if nouveau_mot_de_passe:
            # Génération du hash du nouveau mot de passe
            nouveau_mot_de_passe_hash = generate_password_hash(nouveau_mot_de_passe)
            
            # Mise à jour des informations de l'adhérent dans la base de données
            users_collection.update_one(
                {"_id": adherent['_id']},
                {"$set": {
                    "username": nouveau_nom,
                    "role": nouveau_role,
                    "password": nouveau_mot_de_passe_hash
                }}
            )
        else:
            # Mise à jour des informations de l'adhérent sans changer le mot de passe
            users_collection.update_one(
                {"_id": adherent['_id']},
                {"$set": {
                    "username": nouveau_nom,
                    "role": nouveau_role
                }}
            )
        
        return redirect(url_for('liste_adherents'))
    
    return render_template('modifier_adherent.html', adherent=adherent)

@app.route('/ajouter_adherent', methods=['GET', 'POST'])
@login_required
@admin_required
def ajouter_adherent():
    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role'] 
        password = request.form['password'] # Assurez-vous que le formulaire a un champ pour le rôle

        # Vérifier si l'utilisateur existe déjà
        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            flash("Cet utilisateur existe déjà.")
            return redirect(url_for('ajouter_adherent'))

        # Ajouter l'utilisateur à la base de données
        users_collection.insert_one({"username": username, "role": role,"password":password})

        flash("Utilisateur ajouté avec succès.")
        return redirect(url_for('liste_adherents'))

    return render_template('ajouter_adherent.html')




if __name__ == '__main__':
    app.run(debug=True)
