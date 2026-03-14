"""
About Page - Aptal AI Company Information
Displays company overview, solutions, team, and contact information
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QScrollArea,
    QTextEdit, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QFont, QDesktopServices
import webbrowser


class AboutPage(QWidget):
    """About page with company information"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Setup about page UI"""
        # Main scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1a1a1a;
            }
            QScrollBar:vertical {
                background-color: #222222;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #ffc107;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Content widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(40)

        # Hero Section
        layout.addWidget(self.create_hero_section())

        # Stats Section
        # layout.addWidget(self.create_stats_section())

        # Solutions Section
        layout.addWidget(self.create_solutions_section())

        # Contact Section
        layout.addWidget(self.create_contact_section())

        # Footer
        layout.addWidget(self.create_footer())

        scroll.setWidget(content_widget)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def create_hero_section(self):
        """Create hero section with company tagline"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a1a,
                    stop:1 #222222
                );
                border-radius: 16px;
                padding: 40px;
            }
        """)

        # Container layout
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)

        # --- Brand layout (logo + title) ---
        brand_layout = QHBoxLayout()
        brand_layout.setAlignment(Qt.AlignCenter)
        brand_layout.setSpacing(12)

        # Logo
        logo_label = QLabel()
        pixmap = QPixmap("app/data/logo.png")  # Your logo path
        pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_label.setPixmap(pixmap)
        brand_layout.addWidget(logo_label)

        # Company title
        title_label = QLabel("Aptal AI")
        title_label.setStyleSheet("""
            color: #fff;
            font-size: 42px;
            font-weight: bold;
        """)
        brand_layout.addWidget(title_label)

        layout.addLayout(brand_layout)

        # --- Tagline ---
        tagline = QLabel("Computer Vision Meets Intelligence")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet("""
            color: #ffc107;
            font-size: 32px;
            font-weight: 600;
            margin-top: 20px;
        """)
        layout.addWidget(tagline)

        # --- Description (partially hidden / faded) ---
        description = QLabel(
            "Revolutionary AI-powered solutions for security, attendance, and analytics.\n"
            "Experience the future of intelligent surveillance today."
        )
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        description.setStyleSheet("""
            color: rgba(148, 163, 184, 0.5);  /* Faded / semi-transparent */
            font-size: 16px;
            line-height: 1.6;
            margin-top: 16px;
            max-width: 800px;
        """)
        layout.addWidget(description)

        # --- Action buttons ---
        buttons_layout = QHBoxLayout()
        buttons_layout.setAlignment(Qt.AlignCenter)
        buttons_layout.setSpacing(16)

        explore_btn = QPushButton("Explore Products")
        explore_btn.setObjectName("addApplicationButton")
        explore_btn.clicked.connect(lambda: self.scroll_to_section("solutions"))

        contact_btn = QPushButton("Get in Touch")
        contact_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffc107;
                border: 2px solid #ffc107;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                min-width: 140px;
            }
            QPushButton:hover {
                background-color: #ffc107;
                color: #1a1a1a;
            }
        """)

        buttons_layout.addWidget(explore_btn)
        buttons_layout.addWidget(contact_btn)
        layout.addLayout(buttons_layout)

        return container

    def create_stat_card(self, value, label, color):
        """Create individual stat card"""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(f"""
            color: {color};
            font-size: 36px;
            font-weight: bold;
        """)

        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 14px;
            font-weight: 500;
        """)

        layout.addWidget(value_label)
        layout.addWidget(text_label)

        return card

    def create_solutions_section(self):
        """Create solutions section"""
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setSpacing(24)

        # Section header
        header = QLabel("Our Solutions")
        header.setStyleSheet("""
            color: #fff;
            font-size: 28px;
            font-weight: bold;
            border-bottom: 3px solid #ffc107;
            padding-bottom: 12px;
        """)
        layout.addWidget(header)

        subtitle = QLabel("Cutting-edge AI technology designed to transform security and surveillance")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 15px; margin-bottom: 16px;")
        layout.addWidget(subtitle)

        # Solutions grid
        solutions_grid = QGridLayout()
        solutions_grid.setSpacing(20)

        solutions = [
            {
                "name": "CCTV-Based Realtime Attendance System",
                "description": "Advanced facial recognition technology for seamless, contactless attendance tracking with 99.9% accuracy.",
                "features": ["Real-time Processing", "Cloud Integration", "Multi-location Support"],
                "icon": "📹"
            },
            {
                "name": "Vision-Based Personal AI Agent",
                "description": "Intelligent AI assistant powered by computer vision for personalized user experiences and interactions.",
                "features": ["Natural Interaction", "Context Awareness", "Adaptive Learning"],
                "icon": "🤖"
            },
            {
                "name": "Video Analytics Dashboard",
                "description": "Real-time insights and analytics from video feeds with customizable dashboards and instant alerts.",
                "features": ["Live Monitoring", "Predictive Analytics", "Custom Reports"],
                "icon": "📊"
            },
            {
                "name": "Night-Watcher AI",
                "description": "Revolutionary night security solution with enhanced accuracy for 24/7 perimeter protection.",
                "features": ["Thermal Detection", "Motion Analysis", "Instant Alerts"],
                "icon": "🌙"
            }
        ]

        for i, solution in enumerate(solutions):
            row = i // 2
            col = i % 2
            card = self.create_solution_card(solution)
            solutions_grid.addWidget(card, row, col)

        layout.addLayout(solutions_grid)

        return container

    def create_solution_card(self, solution):
        """Create individual solution card"""
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background-color: #222222;
                border: 1px solid #333333;
                border-radius: 12px;
                padding: 20px;
            }
            QFrame#card:hover {
                border: 1px solid #ffc107;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        # Icon and name
        header_layout = QHBoxLayout()

        icon = QLabel(solution["icon"])
        icon.setStyleSheet("font-size: 32px;")

        name = QLabel(solution["name"])
        name.setStyleSheet("""
            color: #fff;
            font-size: 16px;
            font-weight: bold;
        """)
        name.setWordWrap(True)

        header_layout.addWidget(icon)
        header_layout.addWidget(name, 1)
        layout.addLayout(header_layout)

        # Description
        desc = QLabel(solution["description"])
        desc.setWordWrap(True)
        desc.setStyleSheet("""
            color: #94a3b8;
            font-size: 13px;
            line-height: 1.5;
            margin-top: 8px;
        """)
        layout.addWidget(desc)

        # Features
        for feature in solution["features"]:
            feature_layout = QHBoxLayout()

            bullet = QLabel("✓")
            bullet.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 14px;")

            feature_label = QLabel(feature)
            feature_label.setStyleSheet("color: #e2e8f0; font-size: 13px;")

            feature_layout.addWidget(bullet)
            feature_layout.addWidget(feature_label)
            feature_layout.addStretch()

            layout.addLayout(feature_layout)

        layout.addStretch()

        return card

    def create_team_section(self):
        """Create team section"""
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setSpacing(24)

        # Section header
        header = QLabel("Our Frontier Team")
        header.setStyleSheet("""
            color: #fff;
            font-size: 28px;
            font-weight: bold;
            border-bottom: 3px solid #ffc107;
            padding-bottom: 12px;
        """)
        layout.addWidget(header)

        subtitle = QLabel("A.P.T.A.L. - Applied Pragmatic Technology and Learning AI")
        subtitle.setStyleSheet("color: #ffc107; font-size: 15px; font-weight: 600; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        description = QLabel(
            "Meet the visionaries behind Aptal AI, driving innovation in computer vision and artificial intelligence")
        description.setStyleSheet("color: #94a3b8; font-size: 14px; margin-bottom: 16px;")
        layout.addWidget(description)

        # Team members grid
        team_grid = QHBoxLayout()
        team_grid.setSpacing(20)

        members = [
            {
                "name": "Akash Prasad Mishra",
                "role": "Chief Technology Officer & Chief Financial Officer",
                "id": "APTAL-AI-APM-00047",
                "quote": "We don't build technology to impress — we build it to work.",
                "icon": "👨‍💼"
            },
            {
                "name": "Ankita Mishra",
                "role": "Client Success Manager",
                "id": "APTAL-AI-APM-00088",
                "quote": "Building partnerships, delivering outcomes.",
                "icon": "👩‍💼"
            }
        ]

        for member in members:
            card = self.create_team_card(member)
            team_grid.addWidget(card)

        # Add join team card
        join_card = self.create_join_team_card()
        team_grid.addWidget(join_card)

        layout.addLayout(team_grid)

        # Vision quote
        vision = QLabel('"Innovation happens when brilliant minds come together to solve real problems."')
        vision.setAlignment(Qt.AlignCenter)
        vision.setWordWrap(True)
        vision.setStyleSheet("""
            color: #ffc107;
            font-size: 18px;
            font-style: italic;
            margin-top: 24px;
            padding: 20px;
            background-color: #222222;
            border-left: 4px solid #ffc107;
            border-radius: 8px;
        """)
        layout.addWidget(vision)

        return container

    def create_team_card(self, member):
        """Create individual team member card"""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(12)

        # Avatar
        avatar = QLabel(member["icon"])
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            font-size: 64px;
            background-color: #333333;
            border: 3px solid #ffc107;
            border-radius: 60px;
            padding: 20px;
            min-width: 120px;
            max-width: 120px;
            min-height: 120px;
            max-height: 120px;
        """)

        avatar_container = QHBoxLayout()
        avatar_container.setAlignment(Qt.AlignCenter)
        avatar_container.addWidget(avatar)
        layout.addLayout(avatar_container)

        # Name
        name = QLabel(member["name"])
        name.setAlignment(Qt.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet("""
            color: #fff;
            font-size: 18px;
            font-weight: bold;
            margin-top: 8px;
        """)
        layout.addWidget(name)

        # Role
        role = QLabel(member["role"])
        role.setAlignment(Qt.AlignCenter)
        role.setWordWrap(True)
        role.setStyleSheet("""
            color: #94a3b8;
            font-size: 13px;
            margin-bottom: 8px;
        """)
        layout.addWidget(role)

        # ID Badge
        id_badge = QLabel(member["id"])
        id_badge.setAlignment(Qt.AlignCenter)
        id_badge.setStyleSheet("""
            color: #ffc107;
            font-size: 11px;
            font-weight: bold;
            background-color: #ffc10722;
            padding: 6px 12px;
            border-radius: 12px;
            margin-bottom: 12px;
        """)
        layout.addWidget(id_badge)

        # Quote
        quote = QLabel(f'"{member["quote"]}"')
        quote.setAlignment(Qt.AlignCenter)
        quote.setWordWrap(True)
        quote.setStyleSheet("""
            color: #e2e8f0;
            font-size: 13px;
            font-style: italic;
            padding: 12px;
            background-color: #333333;
            border-radius: 8px;
        """)
        layout.addWidget(quote)

        layout.addStretch()

        return card

    def create_join_team_card(self):
        """Create join team card"""
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #333333,
                    stop:1 #222222
                );
                border: 2px dashed #ffc107;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        icon = QLabel("+")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("""
            color: #ffc107;
            font-size: 72px;
            font-weight: bold;
        """)
        layout.addWidget(icon)

        title = QLabel("Join Our Team")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: #fff;
            font-size: 20px;
            font-weight: bold;
        """)
        layout.addWidget(title)

        subtitle = QLabel("We're always looking for\ntalented individuals")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            color: #94a3b8;
            font-size: 14px;
        """)
        layout.addWidget(subtitle)

        badge = QLabel("BE PART OF THE FUTURE")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("""
            color: #ffc107;
            font-size: 11px;
            font-weight: bold;
            background-color: #ffc10722;
            padding: 8px 16px;
            border-radius: 12px;
            margin-top: 12px;
        """)
        layout.addWidget(badge)

        layout.addStretch()

        return card

    def create_partners_section(self):
        """Create partners section"""
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setSpacing(24)

        # Section header
        header = QLabel("Trusted Partners")
        header.setStyleSheet("""
            color: #fff;
            font-size: 28px;
            font-weight: bold;
            border-bottom: 3px solid #ffc107;
            padding-bottom: 12px;
        """)
        layout.addWidget(header)

        subtitle = QLabel("Leading institutions rely on our AI solutions")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 15px; margin-bottom: 16px;")
        layout.addWidget(subtitle)

        # Partners grid
        partners_grid = QGridLayout()
        partners_grid.setSpacing(16)

        partners = [
            ("🏛️", "DDU University", "Delhi"),
            ("🏫", "Emerald Heights School", "Indore"),
            ("📚", "St. Xavier School", "Mumbai"),
            ("👮", "Maharashtra Police", "Maharashtra")
        ]

        for i, (icon, name, location) in enumerate(partners):
            partner_card = self.create_partner_card(icon, name, location)
            row = i // 2
            col = i % 2
            partners_grid.addWidget(partner_card, row, col)

        layout.addLayout(partners_grid)

        return container

    def create_partner_card(self, icon, name, location):
        """Create individual partner card"""
        card = QFrame()
        card.setObjectName("card")

        layout = QHBoxLayout(card)
        layout.setSpacing(16)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("""
            font-size: 48px;
            min-width: 60px;
            max-width: 60px;
        """)
        layout.addWidget(icon_label)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        name_label = QLabel(name)
        name_label.setStyleSheet("""
            color: #fff;
            font-size: 16px;
            font-weight: bold;
        """)

        location_label = QLabel(location)
        location_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 13px;
        """)

        info_layout.addWidget(name_label)
        info_layout.addWidget(location_label)
        layout.addLayout(info_layout)

        layout.addStretch()

        return card

    def create_contact_section(self):
        """Create contact section"""
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setSpacing(24)

        # Section header
        header = QLabel("Let's Connect")
        header.setStyleSheet("""
            color: #fff;
            font-size: 28px;
            font-weight: bold;
            border-bottom: 3px solid #ffc107;
            padding-bottom: 12px;
        """)
        layout.addWidget(header)

        subtitle = QLabel("Ready to transform your security infrastructure with AI? Get in touch with us today.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 15px; margin-bottom: 16px;")
        layout.addWidget(subtitle)

        # Contact grid
        contact_grid = QGridLayout()
        contact_grid.setSpacing(20)

        # Contact info (left)
        info_card = QFrame()
        info_card.setObjectName("card")
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(20)

        # Address
        info_layout.addWidget(self.create_contact_item(
            "📍", "Address",
            "Crystal IT Park, 10th Floor\nAptal AI"
        ))

        # Phone
        phone_item = self.create_contact_item(
            "📞", "Phone",
            "+91 8878685316\nCEO - Akash Prasad Mishra"
        )
        info_layout.addWidget(phone_item)

        # LinkedIn
        linkedin_btn = QPushButton("🔗 Connect on LinkedIn")
        linkedin_btn.setStyleSheet("""
            QPushButton {
                background-color: #0077b5;
                color: white;
                border: none;
                padding: 12px 16px;
                border-radius: 8px;
                text-align: left;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #006399;
            }
        """)
        linkedin_btn.clicked.connect(self.open_linkedin)
        info_layout.addWidget(linkedin_btn)

        info_layout.addStretch()

        contact_grid.addWidget(info_card, 0, 0)

        # Message form (right)
        form_card = QFrame()
        form_card.setObjectName("card")
        form_layout = QVBoxLayout(form_card)
        form_layout.setSpacing(16)

        form_title = QLabel("Send us a message")
        form_title.setStyleSheet("""
            color: #fff;
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 8px;
        """)
        form_layout.addWidget(form_title)

        # Name input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your Name")
        form_layout.addWidget(self.name_input)

        # Email input
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Your Email")
        form_layout.addWidget(self.email_input)

        # Message input
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Your Message")
        self.message_input.setMinimumHeight(120)
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #222222;
                color: #fff;
                border: 1px solid #333333;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
            }
        """)
        form_layout.addWidget(self.message_input)

        # Send button
        send_btn = QPushButton("Send Message")
        send_btn.setObjectName("addApplicationButton")
        send_btn.clicked.connect(self.send_message)
        form_layout.addWidget(send_btn)

        contact_grid.addWidget(form_card, 0, 1)

        layout.addLayout(contact_grid)

        return container

    def create_contact_item(self, icon, label, value):
        """Create contact information item"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px; min-width: 30px;")

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("""
            color: #94a3b8;
            font-size: 12px;
            font-weight: 500;
        """)

        value_widget = QLabel(value)
        value_widget.setWordWrap(True)
        value_widget.setStyleSheet("""
            color: #fff;
            font-size: 14px;
            font-weight: 500;
        """)

        text_layout.addWidget(label_widget)
        text_layout.addWidget(value_widget)

        layout.addWidget(icon_label)
        layout.addLayout(text_layout)
        layout.addStretch()

        return container

    def create_footer(self):
        """Create footer"""
        footer = QLabel("© 2025 Aptal AI. All rights reserved. | Powered by Computer Vision & AI")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("""
            color: #64748b;
            font-size: 12px;
            padding: 20px;
            background-color: #111111;
            border-radius: 8px;
            margin-top: 20px;
        """)
        return footer

    def scroll_to_section(self, section):
        """Scroll to specific section (placeholder)"""
        print(f"[ABOUT] Scroll to section: {section}")
        # In a real implementation, you would scroll the QScrollArea to the widget

    def open_linkedin(self):
        """Open LinkedIn profile"""
        try:
            webbrowser.open("https://www.linkedin.com/in/akash-prasad-mishra-85a4991b1/")
        except:
            QMessageBox.information(
                self,
                "LinkedIn",
                "Visit us on LinkedIn:\nhttps://aptal-ai.web.app"
            )

    def send_message(self):
        """Send contact message"""
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()
        message = self.message_input.toPlainText().strip()

        if not name or not email or not message:
            QMessageBox.warning(
                self,
                "Incomplete Form",
                "Please fill in all fields before sending."
            )
            return

        # TODO: Implement actual message sending (email API, Firebase, etc.)
        QMessageBox.information(
            self,
            "Message Sent",
            f"Thank you, {name}!\n\n"
            "Your message has been sent successfully.\n"
            "We'll get back to you soon at {email}."
        )

        # Clear form
        self.name_input.clear()
        self.email_input.clear()
        self.message_input.clear()