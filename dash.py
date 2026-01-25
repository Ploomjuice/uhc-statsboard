import ast
import sys

import plotly.express as px
import math
from db_ops import DBOPs
import pandas as pd
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QLineEdit,
    QTextEdit,
    QTextBrowser,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QScrollArea,
    QComboBox,
    QStyledItemDelegate,
    QAbstractScrollArea,
    QGraphicsOpacityEffect
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import QSize, Qt,  QPoint, QUrl, QThread
from PySide6.QtWebEngineWidgets import QWebEngineView
from data_aggregation import FullAggregation
import requests
from db_update import Loader
from datetime import datetime
import numpy as np
from pprint import pprint
from scipy.stats import gaussian_kde
import plotly.graph_objects as go
from collections import defaultdict
from workers import UpdateWorker, SimulatorWorker


class Dashboard(QMainWindow):
    def __init__(self, default=True):
        super().__init__()


        # SEARCH VARS
        # connect to db
        self.api = DBOPs("data/stats.db")
        self.api.conn.execute("PRAGMA journal_mode=WAL;")
        self.api.conn.execute("PRAGMA synchronous=NORMAL;")

        # query and preload player search info
        self.players = self.api.get_players()
        self.rounds = self.api.get_rounds()
        self.fetch = FullAggregation(interface=self.api, update=False)
        self.color_theme = "#8973c6"
        self.not_enough = "#372042"
        self.enough = "#a66ac4"
        self.to_add = []
        self.today = datetime.today()

        # updates
        self.updater = Loader()
        self.unknowns = []

        # tool
        self.redacted_players = self.api.get_redacted()
        # customization json goes here later

        self.opaque = """
                        QComboBox QAbstractItemView {
                            background-color: rgba(30, 30, 30, 220);
                        }
                        """
        # ----- DASH SETUP -----
        self.setWindowTitle("r/ultrahardcore Recorded Round Dashboard")
        self.setFixedSize(1500, 800)

        #self.setBaseSize(QSize(1200,675))
        self.title_font = QFont("Helvetica", 24, QFont.Bold)
        self.desc_font = QFont("Helvetica", 12)
        self.plot_font_color = '#d6d6d6'

        # background
        self.bg = QFrame()
        self.bg.setStyleSheet("QFrame {background-color: #232323}")

        # central widget & root layout
        self.central = QWidget()
        self.central.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(self.central)
        root_layout = QVBoxLayout(self.central)  # vertical: top bar + content

        # Top Bar
        self.top_bar = QWidget()
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(10, 10, 10, 10)

        # Logo
        logo_label = QLabel()
        pixmap = QPixmap("img/32xautumn.png")
        if not pixmap.isNull():
            logo_label.setPixmap(pixmap.scaledToHeight(60))

        # Title
        title_label = QLabel("r/ultrahardcore Statistics Dashboard (Beta)")
        title_font = QFont("Helvetica", 16, QFont.Bold)
        title_label.setFont(title_font)

        # version
        version = QLabel("Version: 0.9.5-beta")
        version_font = QFont("Helvetica", 8)
        version.setFont(version_font)

        # Dark Mode Button
        self.dark_mode_button = QPushButton("☀")
        self.dark_mode_button.setCheckable(True)
        self.dark_mode_button.clicked.connect(self._toggle_dark_mode)
        self.dark_mode = True


        # assemble top bar
        top_layout.addWidget(logo_label)
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(version)
        top_layout.addWidget(self.dark_mode_button)
        #self.top_bar.setStyleSheet("padding: 20px;")

        root_layout.addWidget(self.top_bar)

        # main page (visualizer)
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.addWidget(self.bg)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.addItem(QListWidgetItem("🏠 Home"))
        #self.sidebar.addItem(QListWidgetItem("☘ About"))
        self.sidebar.addItem(QListWidgetItem("🏆 Leaderboards"))
        self.sidebar.addItem(QListWidgetItem("📊 Individual Stats"))
        self.sidebar.addItem(QListWidgetItem("📚 Round Stats"))
        self.sidebar.addItem(QListWidgetItem("💻 Round Simulator"))
        self.sidebar.addItem(QListWidgetItem("⚙ Settings"))

        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: #2e3440;
                color: white;
                border: none;
                font: 14px 'Segoe UI';
            }
            QListWidget::item {
                padding: 10px;
            }
            QListWidget::item:selected {
                background-color: #4c566a;
            }
            QListWidget::item:hover {
                background-color: #434c5e;
            }
        """)



        # add all pages
        self.pages = QStackedWidget()
        self.pages.addWidget(self._make_homepage())
        #self.pages.addWidget(self._make_about())
        self.pages.addWidget(self._make_leaderboard())
        self.pages.addWidget(self._make_player_browser())
        self.pages.addWidget(self._make_round_page())
        self.pages.addWidget(self._make_uhc_sim())
        self.pages.addWidget(self._make_settings())

        # connect sidebar to pages
        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        # assemble page
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)

        root_layout.addWidget(main_content)

        # STARTUP EVENTS

        # dark mode
        self._toggle_dark_mode()

        # # search delay
        # self.search_timer = QTimer()
        # self.search_timer.timeout.connect(self._search)
        # self.search_timer.setSingleShot(True)



# --------------- INFO ----------------
    def _make_homepage(self):
        """
        General Homepage with
        - about program
        - about the dev (me)
            - add points of contact and stuff (discord, youtube)
        -

        :return: homepage lol
        """
        # init content
        content = QWidget()
        layout = QVBoxLayout(content)

        # title
        title_text = QLabel("Home")
        title_text.setFont(self.title_font)
        title_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title_text)

        # Description
        welcome = QLabel("Welcome to the r/ultrahardcore Stats Dashboard!")
        welcome.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        heading_font = QFont("Helvetica", 14)
        welcome.setFont(heading_font)
        layout.addWidget(welcome)

        desc = QLabel(
            """<p>
            This dashboard was developed by <strong><t style="color: #807fd1;"> plumjuice </t></strong>
            as an alternative visualization tool for various stats and other information
            of the r/ultrahardcore community's recorded rounds (RRs), players, 
            and RR gamemodes as extracted from <strong><a href="https://docs.google.com/spreadsheets/d/1cJnD5KPdTL1g_8CkWGiaibcpg00WKa2KgsGHzQnKnc8/edit?usp=sharing",
            style="text-decoration: none; color: #3962dd;">
            @ripperstevem5's Global RR Stats Community Document</a></strong>, 
            with the main goals of convenience and scalability in mind.
            In addition to being a stat viewer, this dashboard also includes some experimental
            potentially (hopefully) useful tools such as a player skill rating system, team builder, and UHC simulator.
            If there is any issue or concern with any aspect of this dashboard, please contact me
            via the methods listed below.  Enjoy!
            </p>
            """
        )
        desc.setOpenExternalLinks(True)
        desc.setWordWrap(True)
        desc.setFont(self.desc_font)
        desc.setStyleSheet("""QLabel {
                                padding: 20;
                                line-height: normal;
                              }
                              QLabel:a {
                                text-decoration: none;
                                color: #676767;
                              }
                           """)
        layout.addWidget(desc)


        # about me
        about_title = QLabel("<h2>Note From the Developer</h2>")
        about_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        about_title.setFont(heading_font)
        layout.addWidget(about_title)

        about = QLabel(
            """
            <h2>Plum</h2>
            <p>(plumjuice)</p>
            <p><strong>Discord: </strong> @plum.juice</p>
            <p><strong>Email: </strong> forplumjuiceuse@gmail.com</p>
            <p><strong>Inquiry Form: </strong><a href="https://forms.gle/vQoz8GHxZHBCgUw8A">link</a></p>
            
            <p>
            hi im plum!  i took a semester off from uni and this was something
            i decided to do to keep myself busy.  alas, i did not get to implement everything i wanted,
            but i'm glad most of what i did get done turned out okay(?).  (please don't pay too
            much mind to the appearance of the dashboard ik it looks ugly) <br><br>
            
            in any case, i never really planned to be really exhaustive with the stats, and
            just wanted to do what felt right in the moment to make this proof of concept.  
            i hope in spite of how scuffed it is, someone will still find some use (or even joy?) 
            out of this.<br><br>
            
            in the future i want to incorporate things like direct player comparisons, appearance customizability,
            alternative charts, and most importantly, write up a sufficient doc for everything in this (which somehow,
            i didn't want to do until it was too late; for now just feel free to ask and hopefully i'll be free enough
            to respond). <br><br>
            
            so yeah, with that just keep in mind that the ratings and simulations are experimental, and that i
            calculated the stats on my own so there may be minor discrepancies between my stats and the official stats. 
            (take everything with a grain of salt)  
            have fun, and don't take this too seriously! 
            
            

            </p>
            """
        )
        about.setWordWrap(True)

        about.setOpenExternalLinks(True)
        about.setFont(self.desc_font)
        pic_text = QWidget()
        bio_layout = QHBoxLayout(pic_text)
        pic_label = QLabel()
        pixmap = QPixmap("img/mi.jpg")
        pic_label.setPixmap(pixmap.scaledToHeight(300))
        bio_layout.setContentsMargins(100, 0, 100, 0)
        bio_layout.addWidget(pic_label)
        bio_layout.addWidget(about)

        layout.addWidget(pic_text)


        # scroll
        layout.addStretch()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)
        scroll_area.setStyleSheet("background: transparent; border: none;")



        return scroll_area

    def _make_about(self):
        """
        tutorial and faq
        :return: about page
        """
        # init content
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("How to Use This Dashboard:")
        title.setFont(self.title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        table_of_contents = QLabel(
            """
            <h3>Table of Contents</h3>
            <ul>About the Tools
                <li>Leaderboard</li>
                <li>Individual Stats</li>
                <li>Player Comparison</li>
                <li>Round Stats</li>
                <li>Round Simulator</li>
            </ul>
            
            """
        )
        table_of_contents.setFont(self.desc_font)
        layout.addWidget(table_of_contents)

        layout.addStretch()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)
        scroll_area.setStyleSheet("background: transparent; border: none;")

        return scroll_area

# --------------- STATS ----------------
    # leaderboard
    def _make_leaderboard(self):
        """
        (save for later update)
        filters:
        - type of variable
            - approximated skill rating
            - kills
                - all players
                - underdog kills/player kills
                - clutch win rate
            - deaths
                -
        - type of round
            - standard
            - objective completion


        :return:
        """


        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        # three pages

        main_board = QWidget()
        main_board_layout = QVBoxLayout(main_board)

        extra_stats = QWidget()
        extra_stats_layout = QVBoxLayout(extra_stats)

        scatter = QWidget()
        scatter_layout = QVBoxLayout(scatter)

        # three bars
        self.bars = QStackedWidget()


        #  ---- MAIN BOARD ----

        title = QLabel("Leaderboard")
        title.setFont(self.title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)


        # Dropdown Choices
        choices = QWidget()
        choices_layout = QHBoxLayout(choices)
        self.stat_select = QComboBox()
        self.stat_select.addItems([
            "Kill Count",  #
            "Death Count",  #
            "Rounds Played",  #
            "Win Count",  #
            "Alive Win Count",  #
            "Dead Win Count",  #
            "Win Rate",  #
            "Kill Record",
            "KDR",  #
            "KPR",  #
            "Top Frag Count",  #
            "Top Frag Rate",  #
            "Ironman Count",  #
            # "Longest Ironman",#
            "Ironman Rate",  #
            "First Damage Count",  #
            "First Damage Rate",  #
            "First Death Count",  #
            "First Death Rate",  #
            "PvE Death Count",  #
            "PvE Death Rate",  #
            "Suicide Count",  #
            "Suicide Rate",  #
            "Team Kill Count",  #

            # "Deadliest Teams"
        ])
        self.stat_select.setFixedWidth(200)
        self.stat_select.currentTextChanged.connect(self._populate_leaderboard)
        self.stat_select.setStyleSheet(self.opaque)

        # year choice
        years = [str(i) for i in range(2012, self.today.year+1)]
        years.append("Lifetime")
        self.year_select = QComboBox()
        self.year_select.addItems(years)
        self.year_select.setCurrentIndex(len(years)-1)
        self.year_select.setFixedWidth(90)
        self.year_select.currentTextChanged.connect(self._populate_leaderboard)
        self.year_select.setStyleSheet(self.opaque)

        # minimum games
        mg = QWidget()
        mg_layout = QHBoxLayout(mg)
        minimum_games_label = QLabel("<h4>Minimum Games Threshold:  </h4>")
        self.minimum_games = QLineEdit()
        self.minimum_games.setFixedWidth(30)
        self.minimum_games.setText("5")
        self.minimum_games.textChanged.connect(self._populate_leaderboard)
        mg_layout.addWidget(minimum_games_label)
        mg_layout.addWidget(self.minimum_games)

        # redacted
        self.redacted = QCheckBox()
        self.redacted.setText("Show Redacted Players")
        self.redacted.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:checked {
                image: url(img/redacted.png)
            }
        """)
        self.redacted.setChecked(False)
        self.redacted.toggled.connect(self._populate_leaderboard)
        # redacted.toggled.connect(self.hide_redacted)

        # choose view
        self.leaderboard_view = QComboBox()
        self.views = ["Main Board", "Extra Stats", "Scatter View"]
        self.leaderboard_view.addItems(self.views)
        self.leaderboard_view.setCurrentText("Main Board")
        self.leaderboard_view.currentTextChanged.connect(self._switch_board)
        self.leaderboard_view.setStyleSheet(self.opaque)

        main_choices = QWidget()
        main_choices_layout = QHBoxLayout(main_choices)
        main_choices_layout.addWidget(self.stat_select)
        main_choices_layout.addWidget(self.year_select)
        main_choices_layout.addWidget(minimum_games_label)
        main_choices_layout.addWidget(self.minimum_games)
        main_choices_layout.addWidget(self.redacted)
        main_choices_layout.addStretch()

        self.bars.addWidget(main_choices)
        choices_layout.addWidget(self.bars)
        choices_layout.addStretch()
        choices_layout.addWidget(self.leaderboard_view)


        #
        all_graphics = QWidget()
        all_graphics_layout = QHBoxLayout(all_graphics)

        # leaderboard (board)


        self.leaderboard = QTableWidget()
        self.leaderboard.setColumnCount(18)

        self.leaderboard.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)

        #main_board_layout.addWidget(choices)
        main_board_layout.addWidget(all_graphics)

        # ---- EXTRA STATS ----

        extra_title = QLabel("Extra Stats")
        extra_title.setFont(self.title_font)
        extra_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # settings
        extra_bar = QWidget()
        bar_layout = QHBoxLayout(extra_bar)

        self.extra_redacted = QCheckBox()
        self.extra_redacted.setText("Show Redacted Players")
        self.extra_redacted.setStyleSheet("""
                    QCheckBox::indicator {
                        width: 18px;
                        height: 18px;
                    }
                    QCheckBox::indicator:checked {
                        image: url(img/redacted.png)
                    }
                """)
        self.extra_redacted.setChecked(False)
        self.extra_redacted.toggled.connect(self._populate_extra_leaderboard)
        self.extra_redacted.toggled.connect(self._populate_deadliest)

        ts_label = QLabel("<h4>Deadliest Party Size: </h4>")
        self.extra_ts = QLineEdit()
        self.extra_ts.setFixedWidth(30)
        self.extra_ts.setText("2")
        self.extra_ts.textChanged.connect(self._populate_deadliest)

        view_label = QLabel("<h4>Order Deadliest Party By:")
        self.deadly_view = QComboBox()
        self.deadly_view.setFixedWidth(100)
        self.deadly_view.addItems(["Kills", '%Roster'])
        self.deadly_view.setCurrentText('kills')
        self.deadly_view.currentTextChanged.connect(self._populate_deadliest)
        self.deadly_view.setStyleSheet(self.opaque)

        bar_layout.addWidget(ts_label)
        bar_layout.addWidget(self.extra_ts)
        bar_layout.addWidget(view_label)
        bar_layout.addWidget(self.deadly_view)
        bar_layout.addWidget(self.extra_redacted)
        bar_layout.addStretch()

        self.bars.addWidget(extra_bar)

        extra_boards = QWidget()
        extra_boards_layout = QHBoxLayout(extra_boards)

        im = QWidget()
        im_layout = QVBoxLayout(im)
        im_label = QLabel("<h3>Top 100 Longest Ironmans</h3>")
        self.longest_im = QTableWidget()
        self.longest_im.setColumnCount(4)
        self.longest_im.setRowCount(100)
        self.longest_im.setHorizontalHeaderLabels(["Player", "Time", "Season", "Date"])
        self.longest_im.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        im_layout.addWidget(im_label)
        im_layout.addWidget(self.longest_im)

        fd = QWidget()
        fd_layout = QVBoxLayout(fd)
        fd_label = QLabel("<h3>Top 100 Latest First Damages</h3>")
        self.latest_fdams = QTableWidget()
        self.latest_fdams.setColumnCount(4)
        self.latest_fdams.setRowCount(100)
        self.latest_fdams.setHorizontalHeaderLabels(["Player", "Time", "Season", "Date"])
        self.latest_fdams.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        fd_layout.addWidget(fd_label)
        fd_layout.addWidget(self.latest_fdams)

        de = QWidget()
        de_layout = QVBoxLayout(de)
        de_label = QLabel("<h3>Top 100 Deadliest Parties in ToX Games</h3>")
        self.deadliest = QTableWidget()
        self.deadliest.setColumnCount(4)
        self.deadliest.setHorizontalHeaderLabels(["Player(s)", "Kills", "%Roster", "Season"])
        self.deadliest.setColumnWidth(0, 300)

        de_layout.addWidget(de_label)
        de_layout.addWidget(self.deadliest)

        extra_boards_layout.addWidget(de, 1)
        extra_boards_layout.addWidget(im, 1)
        extra_boards_layout.addWidget(fd, 1)
        extra_stats_layout.addWidget(extra_boards)


        # scatter


        self.scatter = QWebEngineView()
        self.scatter.setAttribute(Qt.WA_TranslucentBackground, True)
        self.scatter.page().setBackgroundColor(Qt.transparent)


        scatter_features = [
            "Kill Count",
            "Death Count",
            "Rounds Played",
            "Win Count",
            "Alive Win Count",
            "Dead Win Count",
            "Win Rate",
            "KDR",
            "KPR",
            "Top Frag Count",
            "Ironman Count",
            "Ironman Rate",
            "First Damage Count",
            "First Damage Rate",
            "First Death Count",
            "First Death Rate",
            "PvE Death Count",
            "PvE Death Rate",
            "Suicide Count",
            "Suicide Rate",
            "Team Kill Count",
        ]
        x_label = QLabel("<h4>X-Axis: </h4>")
        self.scatter_x = QComboBox()
        self.scatter_x.addItems(scatter_features)
        self.scatter_x.setCurrentText("Death Count")
        self.scatter_x.setFixedWidth(160)
        self.scatter_x.currentTextChanged.connect(self._make_leaderboard_scatter)
        self.scatter_x.setStyleSheet(self.opaque)

        y_label = QLabel("<h4>Y-Axis: </h4>")
        self.scatter_y = QComboBox()
        self.scatter_y.addItems(scatter_features)
        self.scatter_y.setCurrentText("Kill Count")
        self.scatter_y.setFixedWidth(160)
        self.scatter_y.currentTextChanged.connect(self._make_leaderboard_scatter)
        self.scatter_y.setStyleSheet(self.opaque)

        scatter_minimum_games_label = QLabel("<h4>Minimum Rounds Played: </h4>")
        self.scatter_minimum_games = QLineEdit()
        self.scatter_minimum_games.setFixedWidth(60)
        self.scatter_minimum_games.setText('5')
        self.scatter_minimum_games.textChanged.connect(self._make_leaderboard_scatter)


        scatter_bar = QWidget()
        scatter_bar_layout = QHBoxLayout(scatter_bar)
        scatter_bar_layout.addWidget(x_label)
        scatter_bar_layout.addWidget(self.scatter_x)
        scatter_bar_layout.addWidget(y_label)
        scatter_bar_layout.addWidget(self.scatter_y)
        scatter_bar_layout.addWidget(scatter_minimum_games_label)
        scatter_bar_layout.addWidget(self.scatter_minimum_games)
        self.bars.addWidget(scatter_bar)
        scatter_layout.addWidget(self.scatter)

        all_graphics_layout.addWidget(self.leaderboard, 1)
        #all_graphics_layout.addWidget(graphs, 2)

        self.select = QStackedWidget()
        self.select.addWidget(main_board)
        self.select.addWidget(extra_stats)
        self.select.addWidget(scatter)
        self.select.setCurrentIndex(0)



        # assemble
        layout.addWidget(title)
        #layout.addWidget(self.bars)
        layout.addWidget(choices)
        layout.addWidget(self.select)

        # layout.addWidget(all_graphics)


        layout.addStretch()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)
        scroll_area.setStyleSheet("background: transparent; border: none;")


        # default
        self.stats_dict = self.fetch.leaderboard_graph_stats()
        self._populate_leaderboard()
        self._populate_extra_leaderboard()
        self._populate_deadliest()
        self._make_leaderboard_scatter()
        return scroll_area

    def _populate_leaderboard(self):
        stat = self.stat_select.currentText()
        year = self.year_select.currentText()
        stat_dict = self.stats_dict.copy()
        redacted = self.redacted.isChecked()


        minimum = int(self.minimum_games.text())

        if year == "Lifetime":
            self.stat_select.blockSignals(True)
            self.stat_select.clear()
            self.stat_select.addItems([
                "Kill Count",  #
                "Death Count",  #
                "Rounds Played",  #
                "Win Count",  #
                "Alive Win Count",  #
                "Dead Win Count",  #
                "Win Rate",  #
                "KDR",  #
                "KPR",  #
                "Top Frag Count",  #
                "Top Frag Rate",  #
                "Ironman Count",  #
                # "Longest Ironman",#
                "Ironman Rate",  #
                "First Damage Count",  #
                "First Damage Rate",  #
                "First Death Count",  #
                "First Death Rate",  #
                "PvE Death Count",  #
                "PvE Death Rate",  #
                "Suicide Count",  #
                "Suicide Rate",  #
                "Team Kill Count",  #
                "Kill Record"
                # "Deadliest Teams"
            ])
            self.stat_select.setCurrentText(stat)
            self.stat_select.blockSignals(False)

            sort_by = stat_dict[stat]
            try:
                if redacted:
                    raw = {i: v for i, v in sort_by.items() if stat_dict['Rounds Played'][i] >= minimum}
                else:
                    raw = {i: v for i, v in sort_by.items() if stat_dict['Rounds Played'][i] >= minimum and i not in stat_dict['redacted']}
                sorted_data = dict(sorted(raw.items(), key=lambda item: item[1], reverse=True))

            except ValueError:
                sorted_data = dict(sorted(sort_by.items(), key=lambda item: item[1], reverse=True))

            self.leaderboard.setRowCount(len(sorted_data))
            self.leaderboard.setColumnCount(18)
            self.leaderboard.setHorizontalHeaderLabels([
                "Stat Rank",
                "Rounds",
                "Kills",
                "Deaths",
                "Wins (%R)",
                "Alive (%W)",
                "Dead (%W)",
                "Tied (%W)",
                "Kill Record",
                "KDR",
                "KPR",
                "PvE Deaths (%D)",
                "Ironmans (%R)",
                "Top Frags (%R)",
                "First Damages (%R)",
                "First Deaths (%R)",
                "Suicides (%D)",
                "Team Kills"])
            for idx, p in enumerate(sorted_data):
                ign = stat_dict['igns'][p]
                self.leaderboard.setVerticalHeaderItem(idx, QTableWidgetItem(ign))
                self.leaderboard.setItem(idx, 0, QTableWidgetItem(
                    str(idx+1)))
                self.leaderboard.setItem(idx, 1, QTableWidgetItem(
                    str(stat_dict['Rounds Played'][p])))
                self.leaderboard.setItem(idx, 2, QTableWidgetItem(
                    str(stat_dict['Kill Count'][p])))
                self.leaderboard.setItem(idx, 3, QTableWidgetItem(
                    str(stat_dict['Death Count'][p])))
                self.leaderboard.setItem(idx, 4, QTableWidgetItem(
                    str(stat_dict['Win Count'][p])+f' ({stat_dict["Win Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 5, QTableWidgetItem(
                    str(stat_dict['Alive Win Count'][p]) + f' ({stat_dict["Alive Win Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 6, QTableWidgetItem(
                    str(stat_dict['Dead Win Count'][p]) + f' ({stat_dict["Dead Win Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 7, QTableWidgetItem(
                    str(stat_dict['Tied Win Count'][p]) + f' ({stat_dict["Tied Win Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 8, QTableWidgetItem(
                    str(stat_dict['Kill Record'][p])))
                self.leaderboard.setItem(idx, 9, QTableWidgetItem(
                    str(stat_dict['KDR'][p])))
                self.leaderboard.setItem(idx, 10, QTableWidgetItem(
                    str(stat_dict['KPR'][p])))
                self.leaderboard.setItem(idx, 11, QTableWidgetItem(
                    str(stat_dict['PvE Death Count'][p]) + f' ({stat_dict["PvE Death Rate"][p]})%'))
                self.leaderboard.setItem(idx, 12, QTableWidgetItem(
                    str(stat_dict['Ironman Count'][p]) + f' ({stat_dict["Ironman Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 13, QTableWidgetItem(
                    str(stat_dict['Top Frag Count'][p]) + f' ({stat_dict["Top Frag Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 14, QTableWidgetItem(
                    str(stat_dict['First Damage Count'][p]) + f' ({stat_dict["First Damage Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 15, QTableWidgetItem(
                    str(stat_dict['First Death Count'][p]) + f' ({stat_dict["First Death Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 16, QTableWidgetItem(
                    str(stat_dict['Suicide Count'][p]) + f' ({stat_dict["Suicide Rate"][p]}%)'))
                self.leaderboard.setItem(idx, 17, QTableWidgetItem(
                    str(stat_dict['Team Kill Count'][p])))


        else:
            year = f'{year}-01-01'
            sort_by = stat_dict['Yearly '+stat][year]
            try:
                if not redacted:
                    raw = {i: v for i, v in sort_by.items() if
                           stat_dict['Yearly Rounds Played'][year][i] >= minimum}
                else:
                    raw = {i: v for i, v in sort_by.items() if
                           stat_dict['Yearly Rounds Played'][year][i] >= minimum and i not in stat_dict['redacted']}
                sorted_data = dict(sorted(raw.items(), key=lambda item: item[1], reverse=True))

            except ValueError:
                sorted_data = dict(sorted(sort_by.items(), key=lambda item: item[1], reverse=True))

            self.leaderboard.setRowCount(len(sorted_data))
            self.stat_select.blockSignals(True)
            self.stat_select.clear()
            self.stat_select.addItems(["Kill Count",#
                                        "Death Count",#
                                        "Rounds Played",#
                                        "Win Count",#
                                        "Alive Win Count",#
                                        "Dead Win Count",#
                                        "Win Rate", #
                                        "KDR", #
                                        "KPR",
                                        "PvE Death Count",  #
                                        ])
            self.stat_select.setCurrentText(stat)
            self.stat_select.blockSignals(False)
            self.leaderboard.setColumnCount(11)
            self.leaderboard.setHorizontalHeaderLabels([
                "Stat Rank",
                "Rounds",
                "Kills",
                "Deaths",
                "Wins (%R)",
                "Alive (%W)",
                "Dead (%W)",
                "Tied (%W)",
                "KDR",
                "KPR",
                "PvE Deaths (%D)"])


            for idx, p in enumerate(sorted_data):
                ign = stat_dict['igns'][p]

                self.leaderboard.setVerticalHeaderItem(idx, QTableWidgetItem(ign))
                self.leaderboard.setItem(idx, 0, QTableWidgetItem(
                    str(idx+1)))
                self.leaderboard.setItem(idx, 1, QTableWidgetItem(
                    str(stat_dict['Yearly Rounds Played'][year][p])))
                self.leaderboard.setItem(idx, 2, QTableWidgetItem(
                    str(stat_dict['Yearly Kill Count'][year][p])))
                self.leaderboard.setItem(idx, 3, QTableWidgetItem(
                    str(stat_dict['Yearly Death Count'][year][p])))
                self.leaderboard.setItem(idx, 4, QTableWidgetItem(
                    str(stat_dict['Yearly Win Count'][year][p])+f' ({stat_dict["Yearly Win Rate"][year][p]}%)'))
                self.leaderboard.setItem(idx, 5, QTableWidgetItem(
                    str(stat_dict['Yearly Alive Win Count'][year][p]) + f' ({stat_dict["Yearly Alive Win Rate"][year][p]}%)'))
                self.leaderboard.setItem(idx, 6, QTableWidgetItem(
                    str(stat_dict['Yearly Dead Win Count'][year][p]) + f' ({stat_dict["Yearly Dead Win Rate"][year][p]}%)'))
                self.leaderboard.setItem(idx, 7, QTableWidgetItem(
                    str(stat_dict['Yearly Tied Win Count'][year][p]) + f' ({stat_dict["Yearly Tied Win Rate"][year][p]}%)'))
                self.leaderboard.setItem(idx, 8, QTableWidgetItem(
                    str(stat_dict['Yearly KDR'][year][p])))
                self.leaderboard.setItem(idx, 9, QTableWidgetItem(
                    str(stat_dict['Yearly KPR'][year][p])))
                self.leaderboard.setItem(idx, 10, QTableWidgetItem(
                    str(stat_dict['Yearly PvE Death Count'][year][p]) + f' ({stat_dict["Yearly PvE Death Rate"][year][p]}%)'))

    def _populate_extra_leaderboard(self):
        longest_ims = self.stats_dict['Longest Ironman']
        latest_fdams = self.stats_dict['Latest First Damages']
        redacted = self.extra_redacted.isChecked()

        redacted_players = self.stats_dict['redacted']


        if not redacted:
            longest_ims = [i for i in longest_ims if i[0] not in redacted_players]
            latest_fdams = [i for i in latest_fdams if i[0] not in redacted_players]


        for idx, info in enumerate(longest_ims[:100]):
            player, time, season, date = info

            ign = self.stats_dict['igns'][player]
            self.longest_im.setItem(idx, 0, QTableWidgetItem(ign))
            self.longest_im.setItem(idx, 1, QTableWidgetItem(time))
            self.longest_im.setItem(idx, 2, QTableWidgetItem(season))
            self.longest_im.setItem(idx, 3, QTableWidgetItem(date))

        for idx, info in enumerate(latest_fdams[:100]):
            player, time, season, date = info
            ign = self.stats_dict['igns'][player]
            self.latest_fdams.setItem(idx, 0, QTableWidgetItem(ign))
            self.latest_fdams.setItem(idx, 1, QTableWidgetItem(time))
            self.latest_fdams.setItem(idx, 2, QTableWidgetItem(season))
            self.latest_fdams.setItem(idx, 3, QTableWidgetItem(date))

        delegate = QStyledItemDelegate()
        self.longest_im.setItemDelegate(delegate)
        self.latest_fdams.setItemDelegate(delegate)
        self.longest_im.resizeColumnsToContents()
        self.latest_fdams.resizeColumnsToContents()

    def _populate_deadliest(self):
        size = self.extra_ts.text()
        mode = self.deadly_view.currentText()
        deadliest = self.fetch.get_deadliest(size, mode)
        redacted = self.extra_redacted.isChecked()
        redacted_players = [self.stats_dict['igns'][i] for i in self.stats_dict['redacted']]

        rows = 100 if len(deadliest) >= 100 else len(deadliest)
        self.deadliest.setRowCount(rows)

        if not redacted:

            deadliest = [i for i in deadliest if len(set(i[0].split(',')) & set(redacted_players)) == 0]

        for idx, entry in enumerate(deadliest[:100]):
            party, rr, season, kills, pct_killed = entry
            party = ', '.join(party.split(','))
            game = ' '.join([rr, season])
            self.deadliest.setItem(idx, 0, QTableWidgetItem(party))
            self.deadliest.setItem(idx, 1, QTableWidgetItem(str(kills)))
            self.deadliest.setItem(idx, 2, QTableWidgetItem(str(pct_killed)+'%'))
            self.deadliest.setItem(idx, 3, QTableWidgetItem(game))

        #self.deadliest.resizeRowsToContents()
        self.deadliest.resizeColumnsToContents()
        self.deadliest.setWordWrap(True)
        self.deadliest.resizeRowsToContents()

    def _make_leaderboard_scatter(self):
        min_text = self.scatter_minimum_games.text()
        minimum = int(min_text) if min_text else 0
        x_stat = self.scatter_x.currentText()
        y_stat = self.scatter_y.currentText()
        x_dict = {i:v for i, v in self.stats_dict[x_stat].items() if self.stats_dict['Rounds Played'][i] >= minimum}
        y_dict = {i:v for i, v in self.stats_dict[y_stat].items() if self.stats_dict['Rounds Played'][i] >= minimum}

        labels = {pid: self.stats_dict['igns'][pid] for pid in x_dict.keys()}
        data = pd.DataFrame({x_stat: x_dict, y_stat: y_dict, 'ign':labels})

        fig = px.scatter(data, x=x_stat, y=y_stat, hover_name='ign')

        fig.update_layout(
            font_size=8,
            font_color=self.plot_font_color,
            margin=dict(l=5, r=5, t=5, b=5),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title=x_stat,
            yaxis_title=y_stat,
            showlegend=False

        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=False)

        fig_html = self.package_vis(fig.to_html(include_plotlyjs='cdn',
                                                                full_html=False,
                                                                config={'displayModeBar': False}))

        self.scatter.setHtml(fig_html)

    def _switch_board(self):
        change_to = self.leaderboard_view.currentText()
        idx = self.views.index(change_to)
        self.select.setCurrentIndex(idx)
        self.bars.setCurrentIndex(idx)

    # player profile - browser
    def _make_player_browser(self):
        """
        creates main page for browsing profiles
        search bar (fixed)
        scrolling player list (alphabetical, case-insensitive)
        switch to individual player page
        :return: player stats page
        """
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Player Stats - Profile Lookup")
        title.setFont(self.title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        # player search
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Enter a Player's IGN")
        self.search_bar.textChanged.connect(self._search)
        #self.search_bar.textChanged.connect(self._delay)
        layout.addWidget(self.search_bar)

        # default to showing everything
        self.results = self.players

        # subpages
        self.profile_search = self._make_search_results()
        self.profile_view = self._make_user_profile()

        # subpage stack
        self.profile_subpages = QStackedWidget()
        self.profile_subpages.addWidget(self.profile_search)
        self.profile_subpages.addWidget(self.profile_view)
        layout.addWidget(self.profile_subpages)

        layout.addStretch()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)
        scroll_area.setStyleSheet("background: transparent; border: none;")
        return scroll_area

    def _make_search_results(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        # result browser
        self.view_results = QTextBrowser()

        html = "<p>"
        for player in self.results:
            html += f"""<br> <a href='player:{player}' class='link' style=
                        "font: 16px 'Helvetica';
                        text-decoration: none;
                        color: {self.color_theme};
                        ">
                        {player}</a>"""
        self.view_results.setHtml(html)
        self.view_results.setOpenExternalLinks(False)
        self.view_results.anchorClicked.connect(self._link_handle)


        layout.addWidget(self.view_results, stretch=1)
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(10)

        return content

    def _search(self):
        search = self.search_bar.text().strip().lower()
        # handle empty search
        if search == '': # can add effects later but idk
            html = "<p>"
            for player in self.results:
                html += f"""<br> <a href='player:{player}' class='link' style=
                "font: 16px 'Helvetica';
                text-decoration: none;
                color: {self.color_theme};
                ">
                {player}</a>"""
            self.view_results.setHtml(html)


        else:
            # update results
            self.results = [player for player in self.players if search in player.lower()]
            if not self.results:
                html = f"""<h3> No results found for: {search}.</h3> <br> 
                           <p>Please make sure you have typed the username correctly!</p>
                        """
            else:
                html = f"""<h3> Showing results for: {search} </h3> <br>
                        """
                for player in self.results:
                    html += f"""<br> <a href='player:{player}' class='link' style=
                    "font: 16px 'Helvetica';
                    text-decoration: none;
                    color: {self.color_theme};
                    ">
                    {player}</a>"""

            # send to page
            self.view_results.setHtml(html)
            self.profile_subpages.setCurrentWidget(self.profile_search)

    # general handler for everything
    def _link_handle(self, url):
        if type(url) == str:
            url = QUrl(url)
        if url.scheme() == "player":
            name = url.toString().split(":")[1] # extract ign from url
            self._generate_stats(name)
        elif url.scheme() == 'round':
            rr = url.toString().split(":")[1]
            self._generate_round_profile(rr)
        elif url.scheme() == 'season':
            season = url.toString().split(":")[1]
            self._generate_season_profile(season)
        elif url.scheme() == 'roster':
            to_add = url.toString().split(":")[1]
            self._add_row_to_roster(to_add)

    # player profile - page
    def _make_user_profile(self):
        # init
        content = QWidget()
        layout = QHBoxLayout(content)

        # title
        self.profile_label = QLabel()
        self.profile_label.setWordWrap(True)
        layout.addStretch()

        self.pfp_box = QLabel()
        self.skin_explanation = QLabel()

        # Round Info
        round_box = QWidget()
        round_layout = QVBoxLayout(round_box)
        self.debut = QLabel()
        self.last_played = QLabel()
        self.rounds_played = QLabel()
        self.graph_title = QLabel()
        self.choose_year = QComboBox()
        self.choose_year.setStyleSheet(self.opaque)
        self.choose_year.currentTextChanged.connect(self.user_rating_year_update)
        self.rating_graph = QWebEngineView()
        self.rating_graph.setFixedSize(QSize(200,200))
        self.rating_graph.setAttribute(Qt.WA_TranslucentBackground, True)
        self.rating_graph.page().setBackgroundColor(Qt.transparent)
        self.rating_percentile = QLabel()

        round_layout.addWidget(self.debut)
        round_layout.addWidget(self.last_played)
        round_layout.addWidget(self.rounds_played)
        round_layout.addWidget(self.graph_title)
        round_layout.addWidget(self.choose_year)
        round_layout.addWidget(self.rating_graph)
        round_layout.addWidget(self.rating_percentile)

        mid_dim = QSize(50, 135)


        # kills stats
        kills_content = QWidget()
        kills_layout = QVBoxLayout(kills_content)
        self.kill_label = QLabel('<h2>Kill Stats</h2> ')
        self.kill_stats = QLabel()

        # deaths stats
        deaths_content = QWidget()
        deaths_layout = QVBoxLayout(deaths_content)
        self.death_label = QLabel('<h2>Death and Damage</h2> ')
        self.death_stats = QLabel()

        # wins stats
        wins_content = QWidget()
        wins_layout = QVBoxLayout(wins_content)
        self.win_label = QLabel('<h2>Win Stats</h2> ')
        self.win_stats = QLabel()

        # stack list and graph views
        self.win_stack = QStackedWidget()
        # list
        self.win_list_title = QLabel('<h3>List of Wins</h3>')
        win_list_container = QWidget()
        win_list_layout = QVBoxLayout(win_list_container)
        self.win_list = QLabel()
        self.win_list.setWordWrap(True)


        win_scroll = QScrollArea()
        win_scroll.setWidgetResizable(True)
        win_scroll.setFixedWidth(200)
        win_scroll.setFixedHeight(200)
        win_scroll.setWidget(self.win_list)
        self.win_stack.addWidget(win_scroll)

        # graph
        self.win_pie = QWebEngineView()
        self.win_stack.addWidget(self.win_pie)
        self.win_pie.setFixedSize(QSize(200, 180))
        self.win_pie.setAttribute(Qt.WA_TranslucentBackground, True)
        self.win_pie.page().setBackgroundColor(Qt.transparent)

        # toggle button
        self.win_vis_toggle = QPushButton("Show Pie")
        self.win_vis_toggle.clicked.connect(self.toggle_win_vis)

        win_list_layout.addWidget(self.win_stack)

        # bottom vis
        graphs = QWidget()
        graphs_layout = QHBoxLayout(graphs)
        choices = QWidget()
        choices_layout = QVBoxLayout(choices)
        graph_label = QLabel()
        graph_label.setText("<h4>Statistic</h4>")
        self.graph_choose = QComboBox()
        self.graph_choose.addItems(["Kill Count", "Death Count", "Round Count", "KDR", "KPR", "PvE", "Win Count"])
        self.graph_choose.currentIndexChanged.connect(self.create_stat_graph)
        self.graph_choose.setStyleSheet(self.opaque)
        interval_label = QLabel()
        interval_label.setText("<h4>Interval</h4>")
        self.interval_choose = QComboBox()
        self.interval_choose.addItems(['3M', '6M', '12M'])
        self.interval_choose.currentIndexChanged.connect(self.create_stat_graph)
        self.interval_choose.setStyleSheet(self.opaque)

        choices_layout.addWidget(graph_label)
        choices_layout.addWidget(self.graph_choose)
        choices_layout.addWidget(interval_label)
        choices_layout.addWidget(self.interval_choose)
        choices_layout.addStretch()


        self.graph_view = QWebEngineView()
        self.graph_view.setFixedSize(QSize(600, 200))
        self.graph_view.setAttribute(Qt.WA_TranslucentBackground, True)
        self.graph_view.page().setBackgroundColor(Qt.transparent)

        graphs_layout.addWidget(choices)
        graphs_layout.addWidget(self.graph_view)

        right_dim = QSize(40,170)

        # fun stats
        self.nemeses = QWidget()
        nemeses_layout = QVBoxLayout(self.nemeses)
        self.nemeses_label = QLabel('<h3>Nemeses</h3>')
        self.nemeses_list = QLabel()
        self.nemeses_list.setWordWrap(True)
        self.nemeses_list.linkActivated.connect(self._link_handle)

        self.nemeses_display = QScrollArea()
        self.nemeses_display.setWidgetResizable(True)
        self.nemeses_display.setMinimumSize(right_dim)
        self.nemeses_display.setWidget(self.nemeses_list)

        self.rivals = QWidget()
        rivals_layout = QVBoxLayout(self.rivals)
        self.rivals_label = QLabel('<h3>Rivals</h3>')
        self.rivals_list = QLabel()
        self.rivals_list.setWordWrap(True)
        self.rivals_list.linkActivated.connect(self._link_handle)
        self.rivals_display = QScrollArea()
        self.rivals_display.setMinimumSize(right_dim)
        self.rivals_display.setWidgetResizable(True)
        self.rivals_display.setWidget(self.rivals_list)

        self.dominating = QWidget()
        dominating_layout = QVBoxLayout(self.dominating)
        self.dominating_label = QLabel('<h3>Dominating</h3>')
        self.dominating_list = QLabel()
        self.dominating_list.linkActivated.connect(self._link_handle)
        self.dominating_display = QScrollArea()
        self.dominating_display.setWidgetResizable(True)
        self.dominating_display.setMinimumSize(right_dim)

        self.dominating_display.setWidget(self.dominating_list)

        # add widgets to layouts (title/scroll area)
        nemeses_layout.addWidget(self.nemeses_label)
        nemeses_layout.addWidget(self.nemeses_display)
        rivals_layout.addWidget(self.rivals_label)
        rivals_layout.addWidget(self.rivals_display)
        dominating_layout.addWidget(self.dominating_label)
        dominating_layout.addWidget(self.dominating_display)

        kills_layout.addWidget(self.kill_label)
        kills_layout.addWidget(self.kill_stats)
        deaths_layout.addWidget(self.death_label)
        deaths_layout.addWidget(self.death_stats)
        wins_layout.addWidget(self.win_label)
        wins_layout.addWidget(self.win_stats)
        wins_layout.addWidget(self.win_list_title)
        wins_layout.addWidget(self.win_stack)
        wins_layout.addWidget(self.win_vis_toggle)


        # three columns
        kdw = QWidget()
        kdw_layout = QHBoxLayout(kdw)
        kdw_layout.addWidget(kills_content, 2)
        kdw_layout.addWidget(deaths_content, 2)
        kdw_layout.addWidget(wins_content, 2)


        # assemble left
        left_side = QWidget()
        left_layout = QVBoxLayout(left_side)
        left_layout.addWidget(self.profile_label)
        left_layout.addWidget(self.pfp_box)
        left_layout.addWidget(self.skin_explanation)
        left_layout.addWidget(round_box)
        left_layout.addStretch()

        # assemble middle

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(kdw)
        center_layout.addWidget(graphs)
        center_layout.addStretch()

        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        right_layout.addWidget(self.nemeses, 2)
        right_layout.addWidget(self.rivals, 2)
        right_layout.addWidget(self.dominating, 2)


        layout.addWidget(left_side, 3)
        layout.addWidget(center, 9)
        layout.addWidget(right_side, 4)

        return content

    def _generate_stats(self, ign):
        self.search_bar.clear()
        # common things to use (move to init later)
        stat_line_style = """
                              span {
                                font-weight: normal;
                              }
                           """
        current_q = math.ceil(self.today.month/3)
        current_h = math.ceil(current_q/2)
        current_y = self.today.year


        # title things
        self.skin_explanation.setText('')
        self.profile_label.setText(f"<h1>{ign}</h1>")
        self.profile_subpages.setCurrentWidget(self.profile_view)
        self.selected_data = self.fetch.player_profile(ign)
        pprint(self.selected_data)

        # default graphs
        self.win_stack.setCurrentIndex(0)
        self.win_vis_toggle.setText("Show Pie")
        self.choose_year.clear()
        self.create_stat_graph()

        # get skin
        pfp = QPixmap()
        if not self.selected_data['redacted']:
            try:
                uuid = requests.get(url=f"https://api.mojang.com/users/profiles/minecraft/{ign}", timeout=2).json()['id']


            except KeyError:
                pfp = QPixmap("img/questionmark.png")
                self.skin_explanation.setText(
                    f"<p>Can't find {ign}'s skin...<br> Maybe they changed their username?</p>"
                )
            except requests.exceptions.ConnectTimeout or requests.exceptions.ConnectionError or requests.exceptions.ReadTimeout:
                pfp = QPixmap("img/questionmark.png")
                self.skin_explanation.setText(f"""<p>Mojang's API seems to be down...""")

            else:
                skin_request = requests.get(f"https://api.mineatar.io/face/{uuid}?size=32").content
                pfp.loadFromData(skin_request)
        else:
            pfp = QPixmap("img/redacted.png")
            if self.selected_data['redacted'] == 'X':
                self.skin_explanation.setText("<strong>Redacted Player</strong>")
            elif self.selected_data['redacted'] == 'C':
                self.skin_explanation.setText("<strong>Redacted Player</strong> (Cheater)")


        self.pfp_box.setPixmap(pfp.scaledToHeight(192))

        # under profile desc
        self.debut.setText(
            f"""<p class="header"><strong>Debut RR: </strong><br>
                {self.selected_data['debut_rr']} ({self.selected_data['debut_date']})
            
            
            """
        )
        self.last_played.setText(
            f"""<p class="header"><strong>Most Recent RR: </strong><br>
                {self.selected_data['last_rr']} ({self.selected_data['last_played']})</p>
            """)
        style = """
                p {
                    font: 16px;
                }
                .header {
                    font: 24px;
                }
            
        """
        self.last_played.setStyleSheet(style)
        self.rounds_played.setText(
            f"""
                <p class="header"><strong>Rounds Played:</strong><br> {self.selected_data["rounds"]} </p>
            """
        )
        last_active_year = np.max([int(k) for k in self.selected_data["rating"].keys() if not math.isnan(self.selected_data["rating"][k])])
        last_active_idx = list(self.selected_data["rating"].keys()).index(str(last_active_year))
        msg = str(self.selected_data["rating"][str(last_active_year)])
        if self.selected_data["rounds_by_period"]["12M"][last_active_idx] < 5:
            msg += '?'

        self.graph_title.setText("""<p class="header"><strong>Rating:</strong> (beta)</p>""")
        self.choose_year.addItems([k for k in self.selected_data["rating"] if not math.isnan(self.selected_data["rating"][k])])
        self.choose_year.setCurrentText(str(last_active_year))

        self.create_rating_dist(last_active_year)

        # kdw
        kdr_p = self.selected_data['kdr_percentile']
        if type(kdr_p) != float:
            kdr_p_msg = 'N/A'
        else:
            kdr_p_msg = f"Percentile: {round(kdr_p, 1)}"
        kpr_p = self.selected_data['kpr_percentile']
        if type(kpr_p) != float:
            kpr_p_msg = 'N/A'
        else:
            kpr_p_msg = f"Percentile: {round(kpr_p, 1)}"

        percent_fb = round(self.selected_data['first_bloods'] / self.selected_data['rounds']*100, 1)
        percent_tf = round(self.selected_data['top_frags'] / self.selected_data['rounds']*100, 1)

        kdr = round(self.selected_data['kdr'], 3) if self.selected_data['kdr'] != 'inf' else 'inf'

        self.kill_stats.setText(
            f"""
                <p><span id="stat_title"><strong>Lifetime Kills:</span></strong><br>{self.selected_data['kills']}<br><br>
                <span id="stat_title"><strong>Q{current_q} | H{current_h} | {current_y} Kills:</strong></span><br>
                {self.selected_data['kills_by_period']['3M'][-1]} | 
                {self.selected_data['kills_by_period']['6M'][-1]} | 
                {self.selected_data['kills_by_period']['12M'][-1]}<br><br>
                <span id="stat_title"><strong>Lifetime KDR:</strong></span><br>{kdr} 
                ({kdr_p_msg})<br><br>
                <span id="stat_title"><strong>Q{current_q} | H{current_h} | {current_y} KDR:</strong></span><br>
                {round(self.selected_data['kdr_by_period']['3M'][-1], 3)} | 
                {round(self.selected_data['kdr_by_period']['6M'][-1], 3)} | 
                {round(self.selected_data['kdr_by_period']['12M'][-1], 3)} <br><br>
                <span id="stat_title"><strong>Lifetime KPR:</strong></span><br>{round(self.selected_data['kpr'], 3)} 
                ({kpr_p_msg})<br><br>
                <span id="stat_title"><strong>Q{current_q} | H{current_h} | {current_y}</strong></span><br>
                {round(self.selected_data['kpr_by_period']['3M'][-1], 3)} | 
                {round(self.selected_data['kpr_by_period']['6M'][-1], 3)} | 
                {round(self.selected_data['kpr_by_period']['12M'][-1], 3)} <br><br>
                <span id="stat_title"><strong>First Bloods:</strong></span><br>
                {self.selected_data['first_bloods']} ({percent_fb}% of rounds played)<br><br>
                <span id="stat_title"><strong>Top Frags: </strong></span><br>
                {self.selected_data['top_frags']} ({percent_tf}% of rounds played)<br><br>
                <span id="stat_title"><strong>Kill Record: </strong></span><br>{self.selected_data['kill_record']}<br>
                </p>
            """

        )
        self.kill_stats.setStyleSheet(stat_line_style)

        pve_total = np.sum(self.selected_data['pve_by_period']['3M'])
        pve_percent = round(100 * pve_total / self.selected_data['deaths'], 1)

        fdam_rate = round(100 * self.selected_data['first_dmgs']/self.selected_data['rounds'], 1)
        percent_fd = round(100 * math.trunc(self.selected_data['first_deaths'])/self.selected_data['rounds'], 1)
        percent_im = round(100 * self.selected_data['ironmans']/self.selected_data['rounds'], 1)

        self.death_stats.setText(
            f"""
                <p><span id="stat_title"><strong>Lifetime Deaths:</strong></span><br>{self.selected_data['deaths']}<br><br>
                <span id="stat_title"><strong>Q{current_q} | H{current_h} | {current_y} Deaths:</strong></span><br>
                {self.selected_data['deaths_by_period']['3M'][-1]} | 
                {self.selected_data['deaths_by_period']['6M'][-1]} | 
                {self.selected_data['deaths_by_period']['12M'][-1]}<br><br>
                <span id="stat_title"><strong>PvE Deaths:</strong></span><br>{pve_total} ({pve_percent}% of all deaths)<br><br>
                <span id="stat_title"><strong>Suicides:</strong></span><br>{self.selected_data['suicides']}<br><br>
                <span id="stat_title"><strong>Team Kills: </strong></span><br>{self.selected_data['tks']}<br><br>
                <span id="stat_title"><strong>First Death Count:</strong></span><br>
                {math.trunc(self.selected_data['first_deaths'])} ({percent_fd}% of rounds played)<br><br>
                <span id="stat_title"><strong>Ironman Count:</strong></span><br>
                {self.selected_data['ironmans']} ({percent_im}% of rounds played)<br><br>
                <span id="stat_title"><strong>Longest Ironman:</strong></span><br>{self.selected_data['longest_im']}<br><br>
                <span id="stat_title"><strong>First Damage Count:</strong></span><br>{self.selected_data['first_dmgs']} ({fdam_rate}% of rounds)<br>
                </p>
            """

        )
        self.death_stats.setStyleSheet(stat_line_style)

        wpr_percentile = self.selected_data['wpr_percentile']
        if type(wpr_percentile) != float:
            wpr_p_msg = 'N/A'
        else:
            wpr_p_msg = f"Percentile: {round(wpr_percentile, 1)}"
        wins = self.selected_data['total_wins']

        self.win_stats.setText(
            f"""
                <p><span id="stat_title"><strong>Lifetime Wins:</strong></span><br>{wins}<br><br>
                <span id="stat_title"><strong>{current_y} Wins:</strong></span><br>{self.selected_data['yearly_wins'][f"{self.today.year}-01-01"]}<br><br>
                <span id="stat_title"><strong>Lifetime Win Rate:</strong></span><br>{round(100*self.selected_data['wpr'], 2)}%
                ({wpr_p_msg})<br><br>
                </p>
            """
        )

        # WINS

        self.win_stats.setStyleSheet(stat_line_style)

        win_data = [0, 0, 0]
        win_text = "<p>"
        if self.selected_data['alive_wins']:
            for w in self.selected_data['alive_wins']:
                win_text += f"""<span id='alive'>{w}</span><br>"""
                win_data[0] += 1
        if self.selected_data['tied_wins']:
            for tw in self.selected_data['tied_wins']:
                win_text += f"""<span id='tied'>{tw}</span><br>"""
                win_data[1] += 1
        if self.selected_data['dead_wins']:
            for dw in self.selected_data['dead_wins']:
                win_text += f"""<span id='dead'><i>{dw}</i></span><br>"""
                win_data[2] += 1

        self.win_list.setText(win_text+'</p>')
        pie = px.pie({"Status": ['Alive', "Tied", "Dead"], "Wins": win_data},
                     names="Status", values="Wins",
                     width=180, height=180,
                     color="Status"

                     )

        pie.update_traces(
            textinfo="label+percent",
            textposition="inside"
        )

        pie.update_layout(
            font=dict(size=14),
            font_color=self.plot_font_color,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )

        pie_html = pie.to_html(include_plotlyjs='cdn',
                                         full_html=False,
                                         config={'displayModeBar': False})
        html_wrapper = self.package_vis(pie_html)
        self.win_pie.setHtml(html_wrapper)


        # head to heads

        # head-to-head text
        n_list = ""
        nemeses = self.selected_data['nemeses']
        for nemesis in nemeses:
            kills, deaths = nemeses[nemesis]
            line = f"""
                <span id='lose'>{ign}</span>
                {kills}-{deaths} 
                <a href='player:{nemesis}' class='link' id='win'>{nemesis}</a> <br>
                
            """
            n_list += line

        self.nemeses_list.setOpenExternalLinks(False)
        self.nemeses_list.setText("<p><strong>"+n_list+"</strong></p>")

        r_list = ""
        rivals = self.selected_data['rivals']
        for rival in rivals:
            kills, deaths = rivals[rival]
            if kills > deaths:
                line = f"""
                    <span id='win'>{ign}</span>
                    {kills}-{deaths}
                    <a href='player:{rival}' class='link' id='lose'>{rival}</a> <br>
      
                """
            elif deaths > kills:
                line = f"""
                    <span id='lose'>{ign}</span>
                    {kills}-{deaths}
                    <a href='player:{rival}' class='link' id='win'>{rival}</a> <br>
    
                """
            else:
                line = f"""
                        <span id='draw'>{ign}</span>
                        {kills}-{deaths}
                        <a href='player:{rival}' class='link' id='draw'>{rival}</a> <br>

                    """
            r_list += line
        self.rivals_list.setOpenExternalLinks(False)
        self.rivals_list.setText("<p><strong>" + r_list + "</strong></p>")

        d_list = ""
        dominating = self.selected_data['dominating']
        for dominated in dominating:
            kills, deaths = dominating[dominated]
            line = f"""
                    <span id='win'>{ign}</span>
                    {kills}-{deaths} 
                    <a href='player:{dominated}' class='link' id='lose'>{dominated}</a> <br>

                """
            d_list += line
        self.dominating_list.setOpenExternalLinks(False)
        self.dominating_list.setText("<p><strong>" + d_list + "</strong></p>")

    # player profile - visualizations
    def package_vis(self, vis_html):
        html_wrapper = f"""
                                <html>
                                  <head>
                                    <style>
                                      body {{
                                        background-color: transparent;
                                        margin: 0;
                                        overflow: hidden;
                                      }}
                                      html {{
                                        background-color: transparent;
                                      }}
                                    </style>
                                  </head>
                                  <body>
                                    {vis_html}
                                  </body>
                                </html>
                                """
        return html_wrapper

    def toggle_win_vis(self):
        current = self.win_stack.currentIndex()
        if current == 0:
            self.win_stack.setCurrentIndex(1)
            self.win_vis_toggle.setText("Show List")
            self.win_list_title.setText("<h3>Wins Breakdown</h3>")
        else:
            self.win_stack.setCurrentIndex(0)
            self.win_vis_toggle.setText("Show Pie")
            self.win_list_title.setText("<h3>List of Wins</h3>")

    def create_stat_graph(self):



        self.graph_choose.blockSignals(True)
        self.interval_choose.blockSignals(True)

        stat = self.graph_choose.currentText()
        interval = self.interval_choose.currentText()

        if not interval:
            return
        rounds_played = self.selected_data['rounds_by_period'][interval]

        labels = []
        if interval == '3M':
            for period in range(len(rounds_played)):
                quarter = period % 4 + 1
                year = 2012 + math.floor(period/4)
                labels.append(f'{year}-Q{quarter}')
        elif interval == '6M':
            for period in range(len(rounds_played)):
                half = period % 2 + 1
                year = 2012 + math.floor(period/2)
                labels.append(f'{year}-H{half}')
        else:
            last_recorded_year = int(list(self.selected_data["rating"].keys())[-1])
            labels = [str(y) for y in np.arange(2012, last_recorded_year+1, 1).tolist()]

        if stat == 'Win Count':
            labels = [str(y) for y in np.arange(2012, self.today.year + 1, 1).tolist()]
            self.interval_choose.clear()
            self.interval_choose.addItems(['12M'])
            data = self.selected_data['yearly_wins']
        else:
            self.interval_choose.clear()
            self.interval_choose.addItems(['3M', '6M', '12M'])
            self.interval_choose.setCurrentText(interval)
            if stat == 'Kill Count':
                data = self.selected_data['kills_by_period'][interval]
            elif stat == 'KDR':
                data = self.selected_data['kdr_by_period'][interval]
            elif stat == 'KPR':
                data = self.selected_data['kpr_by_period'][interval]
            elif stat == 'Death Count':
                data = self.selected_data['deaths_by_period'][interval]
            elif stat == 'PvE':
                data = self.selected_data['pve_by_period'][interval]
            elif stat == 'Round Count':
                data = self.selected_data['rounds_by_period'][interval]

        if interval == '3M':
            colors = [self.enough if rp >= 2 else self.not_enough for rp in rounds_played]
        elif interval == '6M':
            colors = [self.enough if rp >= 3 else self.not_enough for rp in rounds_played]
        elif interval == '12M':
            colors = [self.enough if rp >= 6 else self.not_enough for rp in rounds_played]

        fig = px.bar(y=data, x=labels)
        fig.update_layout(
            font_size=8,
            font_color=self.plot_font_color,
            margin=dict(l=5, r=5, t=5, b=5),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title='Year',
            yaxis_title=stat,
            showlegend=False

        )
        if stat in ['KDR', 'KPR']:
            fig.update_traces(marker_color=colors)
        else:
            fig.update_traces(marker_color=self.enough)
        fig_html = self.package_vis(fig.to_html(include_plotlyjs='cdn',
                                                                full_html=False,
                                                                config={'displayModeBar': False}))
        self.graph_view.setHtml(fig_html)

        self.graph_choose.blockSignals(False)
        self.interval_choose.blockSignals(False)

    def create_rating_dist(self, last_active_year):
        self.year = last_active_year

        # ALL ratings from that year
        ratings = np.array([r for r in [i[f'{last_active_year}'] for i in self.fetch.yearly_ratings.values()] if not math.isnan(r)])
        player_rating = self.selected_data['rating'][str(last_active_year)]
        player_percentile = round(len([r for r in ratings if r < player_rating])/len(ratings) * 100, 1)
        uncertainty = '?' if self.selected_data['rounds_by_period']['12M'][last_active_year-2012] < 6 else ''
        line = 'dash' if uncertainty == '?' else 'solid'


        kde = gaussian_kde(ratings)
        x = np.linspace(ratings.min(), ratings.max(), 300)
        y = kde(x)

        rating_dist = go.Figure(layout_yaxis_range=[0,np.max(y)+0.1])
        rating_dist.add_trace(go.Histogram(
            x=ratings,
            histnorm='probability density',
            opacity=0.6,
            name="dist"
        ))
        rating_dist.add_trace(go.Scatter(
            x=x,
            y=y,
            marker={'color':'#8f9bea'}

        ))

        # rating_dist = ff.create_distplot(ratings, group_labels=[f'{last_active_year}'], bin_size=5,
        #                                  show_rug=False)

        rating_dist.add_shape(
            type='line',
            x0=player_rating,
            x1=player_rating,
            y0=0,
            y1=1,
            line_width=2,
            line_color='#a6a7e0',
            line=dict(
                dash=line,
            )
        )

        rating_dist.update_layout(
            font_size=8,
            font_color=self.plot_font_color,
            margin=dict(l=5, r=5, t=5, b=5),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title='Rating',
            yaxis_title='Proportion of Players',
            showlegend=False

        )
        rating_dist.update_xaxes(showgrid=False)
        rating_dist.update_yaxes(showgrid=False)

        rating_dist_html = self.package_vis(rating_dist.to_html(include_plotlyjs='cdn',
                                                                full_html=False,
                                                                config={'displayModeBar': False}))

        self.rating_graph.setHtml(rating_dist_html)
        self.rating_percentile.setText(f"""
        <p><strong>{last_active_year} Rating:</strong> 
        {player_rating}{uncertainty} (Percentile: {player_percentile}{uncertainty})</p>
        """)

    def user_rating_year_update(self, text):
        if type(text) is not str:
            return
        else:
            year = int(text)
        self.create_rating_dist(year)

    # round profiles
    def _make_round_page(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        title = QLabel("Round Profiles")
        title.setFont(self.title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        # subpages
        self.round_search = self.round_browser()
        self.round_view = self._make_round_profile()
        self.season_view = self._make_season_profile()

        # subpage stack
        self.round_subpages = QStackedWidget()
        self.round_subpages.addWidget(self.round_search)
        self.round_subpages.addWidget(self.round_view)
        self.round_subpages.addWidget(self.season_view)
        layout.addWidget(self.round_subpages)

        layout.addStretch()

        return content

    def round_browser(self):
        content = QWidget()
        layout = QVBoxLayout(content)

        self.r_search_bar = QLineEdit()
        self.r_search_bar.setPlaceholderText("Search for a Recorded Round:")
        self.r_search_bar.textChanged.connect(self._search_rounds)

        layout.addWidget(self.r_search_bar)

        scrolls = QWidget()
        scrolls_layout = QHBoxLayout(scrolls)

        alive = QWidget()
        self.alive_layout = QVBoxLayout(alive)
        alive_title = QLabel("<h1>Active Rounds:</h1>")
        alive_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # default pop
        alive_rounds = self.updater.alive_df['Round Name']
        msg = "<p>"
        for rr in alive_rounds:
            msg += (f"""<br> <a href='round:{rr}' class='link' style=
                           "font: 16px 'Helvetica';
                           text-decoration: none;
                           color: {self.color_theme};
                           ">
                           {rr}</a>""")
        msg += "</p>"
        self.alive_list = QLabel()
        self.alive_list.setText(msg)
        self.alive_list.linkActivated.connect(self._link_handle)
        alive_scroll = QScrollArea()
        alive_scroll.setWidgetResizable(True)
        alive_scroll.setWidget(self.alive_list)

        self.alive_layout.addWidget(alive_title)
        self.alive_layout.addWidget(alive_scroll)




        dead = QWidget()
        self.dead_layout = QVBoxLayout(dead)
        dead_title = QLabel("<h1>Inactive Rounds:</h1>")
        dead_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        dead_rounds = self.updater.dead_df['Round Name']
        msg = "<p>"
        for rr in dead_rounds:
            msg += f"""<br> <a href='round:{rr}' class='link' style=
                                       "font: 16px 'Helvetica';
                                       text-decoration: none;
                                       color: {self.color_theme};
                                       ">
                                       {rr}</a>"""
        msg += "</p>"
        self.dead_list = QLabel()
        self.dead_list.setText(msg)
        self.dead_list.linkActivated.connect(self._link_handle)

        dead_scroll = QScrollArea()
        dead_scroll.setWidgetResizable(True)
        dead_scroll.setWidget(self.dead_list)



        self.dead_layout.addWidget(dead_title)
        self.dead_layout.addWidget(dead_scroll)

        scrolls_layout.addWidget(alive)
        scrolls_layout.addWidget(dead)

        layout.addWidget(scrolls)
        return content

    def _search_rounds(self):
        # default
        search = self.r_search_bar.text().strip().lower()
        alive = self.updater.alive_df['Round Name']
        dead = self.updater.dead_df['Round Name']


        alive_msg = "<p>"
        for rr in alive:
            alive_msg += (f"""<br> <a href='round:{rr}' class='link' style=
                                   "font: 16px 'Helvetica';
                                   text-decoration: none;
                                   color: {self.color_theme};
                                   ">
                                   {rr}</a>""")
        alive_msg += "</p>"

        dead_msg = "<p>"
        for rr in dead:
            dead_msg += f"""<br> <a href='round:{rr}' class='link' style=
                                               "font: 16px 'Helvetica';
                                               text-decoration: none;
                                               color: {self.color_theme};
                                               ">
                                               {rr}</a>"""
        dead_msg += "</p>"

        if self.r_search_bar.text() == '':
            self.alive_list.setText(alive_msg)
            self.dead_list.setText(dead_msg)
        else:
            alive_results = [rr for rr in alive if search in rr.lower()]
            if not alive_results:
                msg = f"<h3> No results found for: {search}</h3> <br> "
            else:
                msg = f"<h3> Showing results for: {search}</h3> <p>"
                for rr in alive_results:
                    msg += f"""<br> <a href='round:{rr}' class='link' style=
                                                    "font: 16px 'Helvetica';
                                                    text-decoration: none;
                                                    color: {self.color_theme};
                                                    ">
                                                    {rr}</a>"""

            self.alive_list.setText(msg + "</p>")

            dead_results = [rr for rr in dead if search in rr.lower()]
            if not dead_results:
                msg = f"<h3> No results found for: {search}</h3> <br> "
            else:
                msg = f"<h3> Showing results for: {search} </h3><p>"
                for rr in dead_results:
                    msg += f"""<br> <a href='round:{rr}' class='link' style=
                                                           "font: 16px 'Helvetica';
                                                           text-decoration: none;
                                                           color: {self.color_theme};
                                                           ">
                                                           {rr}</a>"""
            self.dead_list.setText(msg + "</p>")

    def _make_round_profile(self):
        content = QWidget()
        layout = QVBoxLayout(content)

        # title
        back_button = QPushButton("Back")
        back_button.clicked.connect(self.back)
        back_button.setFixedWidth(120)
        self.round_label = QLabel()
        self.round_label.setWordWrap(True)

        # main
        main = QWidget()
        main_layout = QHBoxLayout(main)

        # text side
        left_side = QWidget()
        left_layout = QVBoxLayout(left_side)

        stats_title = QLabel("<h2>Basic Statistics</h2>")
        stats = QWidget()
        stats_layout = QHBoxLayout(stats)
        self.stats_left = QLabel()
        self.stats_right = QLabel()
        stats_layout.addWidget(self.stats_left)
        stats_layout.addWidget(self.stats_right)



        season_title = QLabel("<h2>Browse Seasons</h2>")
        self.season_list = QLabel()
        season_scroll = QScrollArea()
        season_scroll.setWidgetResizable(True)
        self.season_list.setOpenExternalLinks(False)
        self.season_list.linkActivated.connect(self._link_handle)
        season_scroll.setFixedSize(400, 128)
        season_scroll.setWidget(self.season_list)

        # assemble text side
        left_layout.addWidget(stats_title)
        left_layout.addWidget(stats, 7)
        left_layout.addWidget(season_title)
        left_layout.addWidget(season_scroll, 2)


        # graphs side
        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        roster_size_title = QLabel("<h2>Player Count Per Season</h2>")
        self.roster_size_graph = QWebEngineView()
        self.roster_size_graph.setAttribute(Qt.WA_TranslucentBackground, True)
        self.roster_size_graph.page().setBackgroundColor(Qt.transparent)
        self.roster_size_graph.setFixedSize(600, 240)
        player_skill_title = QLabel("<h2>Player Rating Distribution Per Season</h2>")
        self.player_skill_dist = QWebEngineView()
        self.player_skill_dist.setAttribute(Qt.WA_TranslucentBackground, True)
        self.player_skill_dist.page().setBackgroundColor(Qt.transparent)
        self.player_skill_dist.setFixedSize(600, 240)

        right_layout.addWidget(roster_size_title)
        right_layout.addWidget(self.roster_size_graph)
        right_layout.addWidget(player_skill_title)
        right_layout.addWidget(self.player_skill_dist)

        main_layout.addWidget(left_side, 2)
        main_layout.addWidget(right_side, 3)

        layout.addWidget(back_button)
        layout.addWidget(self.round_label)
        layout.addWidget(main)
        layout.addStretch()
        return content

    def _generate_round_profile(self, rr):
        self.round_dict = self.fetch.round_profile(rr)
        self.round_subpages.setCurrentWidget(self.round_view)
        self.round_label.setText(f"<h1>{rr}</h1>")

        self.stats_left.setText(f"""
            <h4>Number of Seasons</h4>
            <p>{self.round_dict['season_count']}</p>
            <h4>Average Episode Count</h4>
            <p>{self.round_dict['avg_eps']}</p>
            <h4>Latest Season Release</h4>
            <p>{self.round_dict['season_dates'][-1]}</p>
            <h4>Days Since Last Season</h4>
            <p>{self.round_dict['since_last_season']}</p>
            <h4>Release Date of First Season</h4>
            <p>{self.round_dict['season_dates'][0]}</p>
            
        """)
        year = self.round_dict['latest_year']
        self.stats_right.setText(f"""
            <h4>Total Unique Players</h4>
            <p>{self.round_dict['roster_size']}</p>
            <h4>Median Rating ({year})</h4>
            <p>{round(self.round_dict['median_ratings'][-1], 2)}</p>
            <h4>Mean Rating ({year})</h4>
            <p>{round(self.round_dict['mean_ratings'][-1], 2)}</p>
            <h4>Rating Standard Deviation ({year})</h4>
            <p>{round(self.round_dict['std_ratings'][-1], 2)}</p>
            <h4>PvE Death Rate (% of Deaths)</h4>
            <p>{self.round_dict['percent_pve']}%</p>
            
        """)

        seasons_msg = "<p>"
        for s in self.round_dict['seasons']:
            seasons_msg += f"""<a href='season:{rr}_{s}'>{rr} {s}</a><br>"""
        seasons_msg += '</p>'
        self.season_list.setText(seasons_msg)
        self.create_roster_graph()
        self.create_rr_ratings_graph()

    # round profiles - graphs
    def create_roster_graph(self):
        x = self.round_dict['seasons']
        y = self.round_dict['players_by_season']
        fig = px.bar(x=x, y=y)
        fig.update_layout(
            font_size=8,
            font_color=self.plot_font_color,
            margin=dict(l=5, r=5, t=5, b=5),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title='Season',
            yaxis_title='Number of Participants',
            showlegend=False
        )
        fig_html = self.package_vis(fig.to_html(include_plotlyjs='cdn',
                                                full_html=False,
                                                config={'displayModeBar': False}))
        self.roster_size_graph.setHtml(fig_html)

    def create_rr_ratings_graph(self):

        rosters = self.round_dict['season_rosters']

        seasons = self.round_dict['seasons']
        player_ratings = self.round_dict['player_ratings']
        years = [d[:4] for d in self.round_dict['season_dates']]
        ratings_by_season = [[player_ratings[p][years[i]] for p in rosters[i]] for i in range(len(years))]

        a = {seasons[i]:ratings_by_season[i] for i in range(len(seasons))}
        fig = go.Figure()
        for i in range(len(seasons)):
            fig.add_trace(go.Violin(
                y=a[seasons[i]],
                name=str(seasons[i])
            )

            )

        fig.update_layout(
            font_size=8,
            font_color=self.plot_font_color,
            margin=dict(l=5, r=5, t=5, b=5),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title='Season',
            yaxis_title='Rating Distribution',
            showlegend=False
        )
        fig_html = self.package_vis(fig.to_html(include_plotlyjs='cdn',
                                                full_html=False,
                                                config={'displayModeBar': False}))

        self.player_skill_dist.setHtml(fig_html)

    # round profiles - season profiles
    def _make_season_profile(self):
        content = QWidget()
        layout = QVBoxLayout(content)

        # title
        back_button = QPushButton("Back")
        back_button.clicked.connect(self.back)
        back_button.setFixedWidth(120)
        self.season_label = QLabel()
        self.season_label.setWordWrap(True)
        self.season_label.setFont(self.title_font)
        self.season_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # main
        main = QWidget()
        main_layout = QHBoxLayout(main)

        # left (game info, game modes)
        info = QWidget()
        info_layout = QVBoxLayout(info)

        # content
        game_info_title = QLabel("<h2>General Info</h2>")
        self.game_info = QLabel()
        game_mode_title = QLabel("<h2>Game Modes</h2>")
        self.game_mode_list = QLabel()
        sig_stats_title = QLabel("<h2>Notable Stats</h2>")
        self.sig_stats = QLabel()
        self.sig_stats.setWordWrap(True)
        newcomers_container = QWidget()
        newcomers_layout = QVBoxLayout(newcomers_container)
        newcomers_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        newcomers_title = QLabel("<h2>Newcomers</h2>")
        self.newcomers = QLabel()
        newcomers_layout.addWidget(self.newcomers)
        newcomers_scroll = QScrollArea()
        newcomers_scroll.setWidget(newcomers_container)
        newcomers_scroll.setFixedHeight(220)
        newcomers_scroll.setWidgetResizable(True)

        info_layout.addWidget(game_info_title)
        info_layout.addWidget(self.game_info)
        info_layout.addWidget(game_mode_title)
        info_layout.addWidget(self.game_mode_list)
        info_layout.addWidget(sig_stats_title)
        info_layout.addWidget(self.sig_stats)
        info_layout.addWidget(newcomers_title)
        info_layout.addWidget(newcomers_scroll)

        info_layout.addStretch()


        # middle column
        placement = QWidget()
        placement_layout = QVBoxLayout(placement)
        placement_title = QLabel("<h2>Placement Ranking</h2><br>")


        # placement-based
        self.placement_kills = QTableWidget()
        self.placement_kills.setColumnCount(3)
        #self.placement_kills.setFixedHeight(300)
        self.placement_kills.setColumnWidth(0, 280)
        self.placement_kills.setColumnWidth(1, 60)
        self.placement_kills.setColumnWidth(2, 90)

        # kill count ranking
        kills_title = QLabel("<br><h2>Kills Ranking</h2>")
        self.kill_ranking = QTableWidget()
        self.kill_ranking.setColumnCount(3)
        self.kill_ranking.setHorizontalHeaderLabels(["Player(s)", "Kills", "% of Roster"])
        #self.kill_ranking.setFixedHeight(300)
        self.kill_ranking.setColumnWidth(0, 280)
        self.kill_ranking.setColumnWidth(1, 60)
        self.kill_ranking.setColumnWidth(2, 90)

        placement_layout.addWidget(placement_title)
        placement_layout.addWidget(self.placement_kills)
        placement_layout.addWidget(kills_title)
        placement_layout.addWidget(self.kill_ranking)
        placement_layout.addStretch()

        kills = QWidget()
        kills_layout = QVBoxLayout(kills)
        kill_feed_title = QLabel("<h2>Kill Feed</h2><br>")
        self.kill_feed = QTableWidget()
        self.kill_feed.setColumnCount(3)
        #self.kill_feed.setFixedHeight(640)
        self.kill_feed.setHorizontalHeaderLabels(["Player", "Death Message", "Killer"])
        self.kill_feed.setColumnWidth(0, 120)
        self.kill_feed.setColumnWidth(1, 200)
        self.kill_feed.setColumnWidth(2, 120)

        kills_layout.addWidget(kill_feed_title)
        kills_layout.addWidget(self.kill_feed)

        main_layout.addWidget(info, 1)
        main_layout.addWidget(placement, 2)
        main_layout.addWidget(kills, 2)


        layout.addWidget(back_button)
        layout.addWidget(self.season_label)
        layout.addWidget(main)

        return content

    def _generate_season_profile(self, season):
        rr, season_no = season.split("_")
        self.round_subpages.setCurrentWidget(self.season_view)

        self.season_dict = self.fetch.season_profile(rr, season_no)
        self.season_label.setText(f"{rr} {season_no}")
        self.placement_kills.clear()
        self.kill_feed.clearContents()

        # game info, stuff
        if self.season_dict['team_size'] == "X":
            ts_msg = ""
        else:
            ts_msg = f" (To{self.season_dict['team_size']})"
        self.game_info.setText(f"""
            <p>
            <span id='header'><strong>Season Alias: </strong>{self.season_dict['alias']}<br>
            <span id='header'><strong>Release Date: </strong>{self.season_dict['date']}<br>
            <span id='header'><strong>Episodes: </strong>{self.season_dict['eps']}<br>
            <span id='header'><strong>Version: </strong>{self.season_dict['version']}<br>
            <span id='header'><strong>Team Type: </strong>{self.season_dict['team_type']}{ts_msg}<br>
            </p>
        """)

        # game modes
        gm_msg = "<p>"
        for i in self.season_dict['gamemodes']:
            gm_msg += f'<br>{i}'

        self.game_mode_list.setText(gm_msg+'<br></p>')

        # stats
        self.sig_stats.setText(f"""
            <p>
            <span id='header'><strong>Ironman: </strong>{self.season_dict['ironman']} ({self.season_dict['ironman_time']})<br>
            <span id='header'><strong>First Damage: </strong>{self.season_dict['first_damage']} ({self.season_dict['first_damage_time']})<br>
            </p>
        """)

        newcomers_msg = "<p>"
        for i in sorted(self.season_dict['newcomers'], key=lambda i: i.lower()):
            newcomers_msg += f"<br>{i}"

        self.newcomers.setText(newcomers_msg+"</p>")

        # placement + kills
        idx = self.round_dict['seasons'].index(season_no)
        roster = self.round_dict['season_rosters'][idx]

        if self.season_dict["team_type"] == "FFA":

            self.placement_kills.setHorizontalHeaderLabels(["Player", "Kills", "% of Roster"])
            self.placement_kills.setRowCount(len(roster))

            for i in range(len(roster)):
                p, kills = list(self.season_dict['ffa_kills'].items())[i]
                percent = round(100 * kills / len(self.round_dict['season_rosters'][idx]), 1)
                self.placement_kills.setItem(i, 0, QTableWidgetItem(str(p)))
                self.placement_kills.setItem(i, 1, QTableWidgetItem(str(kills)))
                self.placement_kills.setItem(i, 2, QTableWidgetItem(str(percent)+'%'))


        else:
            self.placement_kills.setHorizontalHeaderLabels(["Team", "Kills", "% of Roster"])
            self.placement_kills.setRowCount(len(self.season_dict['team_placement']))

            for i in range(len(self.season_dict['team_placement'])):
                team = self.season_dict['team_placement'][i]
                players = ', '.join(self.season_dict['teams'][team])
                kills = self.season_dict['team_kills'][team]
                percent = round(100*kills/len(self.round_dict['season_rosters'][idx]), 1)

                self.placement_kills.setItem(i, 0, QTableWidgetItem(str(players)))
                self.placement_kills.setItem(i, 1, QTableWidgetItem(str(kills)))
                self.placement_kills.setItem(i, 2, QTableWidgetItem(str(percent)+'%'))

        kill_counts = self.season_dict['ffa_kills']
        elimination_groups = {kc: [i for i in kill_counts.keys() if kill_counts[i] == kc] for kc in kill_counts.values()}
        elimination_groups = dict(sorted(elimination_groups.items(), reverse=True))

       #pprint(elimination_groups)
        self.kill_ranking.setRowCount(len(elimination_groups))
        for i, (kc, group) in enumerate(list(elimination_groups.items())):
            kp = round(100*kc/len(self.season_dict['kill_feed']), 1)
            self.kill_ranking.setItem(i, 0, QTableWidgetItem(', '.join(group)))
            self.kill_ranking.setItem(i, 1, QTableWidgetItem(str(kc)))
            self.kill_ranking.setItem(i, 2, QTableWidgetItem(str(kp)+'%'))



        delegate = QStyledItemDelegate()
        self.placement_kills.setItemDelegate(delegate)
        self.placement_kills.resizeRowsToContents()
        self.kill_ranking.setItemDelegate(delegate)
        self.kill_ranking.resizeRowsToContents()
        self.kill_feed.setItemDelegate(delegate)
        self.kill_feed.resizeRowsToContents()
        # kill feed
        self.kill_feed.setRowCount(len(self.season_dict['kill_feed']))
        for i, row in enumerate(self.season_dict['kill_feed']):

            # dead player
            self.kill_feed.setItem(i, 0, QTableWidgetItem(row[0]))

            # death_msg
            self.kill_feed.setItem(i, 1, QTableWidgetItem(row[1]))

            # killer
            if row[4] and row[2]:
                self.kill_feed.setItem(i, 2, QTableWidgetItem(f"{row[4]} ({row[2]})"))
            elif row[2]:
                self.kill_feed.setItem(i, 2, QTableWidgetItem(row[2]))
            elif row[3] and row[3] != "Nothing":
                self.kill_feed.setItem(i, 2, QTableWidgetItem(row[3]))
            elif not row[1]:
                self.kill_feed.setItem(i, 2, QTableWidgetItem("Nothing"))

    # round profile nav
    def back(self):
        current_page = self.round_subpages.currentIndex()
        self.round_subpages.setCurrentIndex(current_page-1)

    def _make_uhc_sim(self):
        content = QWidget()
        layout = QVBoxLayout(content)

        title = QLabel("Team Builder and Round Simulator")
        title.setFont(self.title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        columns = QWidget()
        columns_layout = QHBoxLayout(columns)

        # left side browser
        player_search = QWidget()
        player_search_layout = QVBoxLayout(player_search)
        player_search_label = QLabel("<h3>Add Player to Roster: </h3>")
        self.player_search_line = QLineEdit()
        self.player_search_line.setPlaceholderText("Enter Player IGN: ")
        self.player_search_results = QLabel()
        self.player_search_results.setOpenExternalLinks(False)
        self.player_search_results.linkActivated.connect(self._link_handle)
        self.player_search_line.textChanged.connect(self._fill_simulator_browser)

        self.include_redacted = QCheckBox()
        self.include_redacted.setText("Show Redacted Players")
        self.include_redacted.toggled.connect(self._fill_simulator_browser)
        player_scroll = QScrollArea()
        player_scroll.setWidgetResizable(True)
        player_scroll.setWidget(self.player_search_results)

        player_search_layout.addWidget(player_search_label)
        player_search_layout.addWidget(self.include_redacted)
        player_search_layout.addWidget(self.player_search_line)
        player_search_layout.addWidget(player_scroll)

        # middle (roster, recommendations, edits)
        roster_view = QWidget()
        roster_view_layout = QVBoxLayout(roster_view)
        settings_label = QLabel("<h3>Table Settings</h3>")
        note = QLabel("""<p>Note: Ratings are left adjustable as they are experimental and based on last year of activity,
                      please feel free to change them to your discretion (keep in mind that a score difference of 10
                      results in about a 76% chance to win an equal fight for a higher-rated player, and that for me,
                      the typical player has a rating of around 14-16).  Also, any player with a team name left blank will
                      be treated as a solo.""")
        note.setWordWrap(True)

        settings_bar = QWidget()
        settings_bar_layout = QHBoxLayout(settings_bar)
        # list of settings
        order_by_label = QLabel("<h4>Regroup by Team:</h4>")
        self.order_choices = QPushButton("Sort Table")
        self.order_choices.clicked.connect(self._arrange_roster_table)
        self.order_choices.setFixedWidth(90)
        sort_container = QWidget()
        sort_layout = QVBoxLayout(sort_container)
        sort_layout.addWidget(order_by_label)
        sort_layout.addWidget(self.order_choices)
        # sort_layout.addStretch()


        n_sims_label = QLabel("<h4>Number of Simulations: </h4>")
        self.n_sims = QLineEdit()
        self.n_sims.setText('1')
        self.n_sims.setFixedWidth(90)
        n_sims_container = QWidget()
        n_sims_layout = QVBoxLayout(n_sims_container)
        n_sims_layout.addWidget(n_sims_label)
        n_sims_layout.addWidget(self.n_sims)
        # n_sims_layout.addStretch()



        settings_bar_layout.addWidget(sort_container)
        settings_bar_layout.addWidget(n_sims_container)




        roster_view_label = QLabel("<h3>Current Roster</h3>")

        self.roster_table = QTableWidget()
        self.roster_table.setColumnCount(7)
        self.roster_table.setHorizontalHeaderLabels(["Team",
                                                     "Rating",
                                                     "Rounds Played",
                                                     "Kills Per Round",
                                                     "Win Rate",
                                                     "PvE Death Rate",
                                                     "(Delete)"])

        # self.roster_table.setColumnHidden(5, True)
        # self.roster_table.setColumnHidden(6, True)
        # self.roster_table.setColumnHidden(7, True)
        # self.roster_table.setColumnHidden(8, True)

        # simulate button
        self.sim_button = QPushButton("Run")
        self.sim_button.setFixedWidth(200)
        self.sim_button.clicked.connect(self.simulate)
        self.sim_message = QLabel()

        roster_view_layout.addWidget(settings_label)
        roster_view_layout.addWidget(note)
        roster_view_layout.addWidget(settings_bar)
        roster_view_layout.addWidget(roster_view_label)
        roster_view_layout.addWidget(self.roster_table)
        roster_view_layout.addWidget(self.sim_button)
        roster_view_layout.addWidget(self.sim_message)

        # right side (simulator)
        simulator_view = QWidget()
        simulator_view_layout = QVBoxLayout(simulator_view)
        test_label = QLabel("<h3>RR Trial Killfeed</h3>")
        self.test_round = QTableWidget()
        self.test_round.setColumnCount(3)
        self.test_round.setHorizontalHeaderLabels(["Player", "Death Message", "Killer"])
        chances_label = QLabel("<h3>Simulation Stats</h3>")
        self.simulator_probs = QTableWidget()
        self.simulator_probs.setColumnCount(5)
        self.simulator_probs.setHorizontalHeaderLabels(['Player',
                                                        'Team',
                                                        'Avg Kills',
                                                        'Placement (I (T))',
                                                        'Wins (%)'])


        simulator_view_layout.addWidget(test_label)
        simulator_view_layout.addWidget(self.test_round)
        simulator_view_layout.addWidget(chances_label)
        simulator_view_layout.addWidget(self.simulator_probs)



        columns_layout.addWidget(player_search, 2)
        columns_layout.addWidget(roster_view, 7)
        columns_layout.addWidget(simulator_view, 6)


        layout.addWidget(title)
        layout.addWidget(columns)
        self._fill_simulator_browser()
        return content

    def _fill_simulator_browser(self):
        search = self.player_search_line.text().lower()
        redacted = self.include_redacted.isChecked()
        if not redacted:
            subset = [p for p in self.players if search in p.lower() and p not in self.redacted_players]
        else:
            subset = [p for p in self.players if search in p.lower()]
        html = "<p>"
        for player in subset:
            html += f"""<br> <a href='roster:{player}' class='link' style=
                                        "font: 16px 'Helvetica';
                                        text-decoration: none;
                                        color: {self.color_theme};
                                        ">
                                        {player}</a>"""



        self.player_search_results.setText(html+'</p>')

    def _add_row_to_roster(self, player=None):
        pve, rounds, kpr, wpr, (year, rating) = self.fetch.simple_player_stats(player)
        rating_msg = str(rating) if year == str(self.today.year) and rounds >= 5 else str(rating)+'?'


        if not player: # for later: adding unknown players
            wr_w = QLineEdit()
            wr_w.textChanged.connect(self.roster_table.setItem(
                0, 7, QTableWidgetItem(wr_w.text())
            ))

            pve_w = QLineEdit()
            pve_w.textChanged.connect(self.roster_table.setItem(
                0, 8, QTableWidgetItem(pve_w.text())
            ))

            kpr_w = QLineEdit()
            kpr_w.textChanged.connect(self.roster_table.setItem(
                0, 8, QTableWidgetItem(kpr_w.text())
            ))
            r_w = QLineEdit()

        else:
            wr_w = QTableWidgetItem(str(round(100*wpr, 2))+'%')
            pve_w = QTableWidgetItem(str(pve)+'%')
            kpr_w = QTableWidgetItem(str(round(kpr, 2)))
            r_w = QTableWidgetItem(str(rounds))

        last = self.roster_table.rowCount()
        self.roster_table.insertRow(last)

        delete = QPushButton("Delete")
        delete.clicked.connect(self._delete_from_roster)

        self.roster_table.setCellWidget(last, 0, QLineEdit())
        self.roster_table.setCellWidget(last, 1, QLineEdit())
        self.roster_table.cellWidget(last, 1).setText(rating_msg)
        self.roster_table.setItem(last, 2, r_w)
        self.roster_table.setItem(last, 3, kpr_w)
        self.roster_table.setItem(last, 4, wr_w)
        self.roster_table.setItem(last, 5, pve_w)

        self.roster_table.setCellWidget(last, 6, delete)
        self.roster_table.setVerticalHeaderItem(last, QTableWidgetItem(player))

    def _delete_from_roster(self): # i chatgpt'd this bc i was lazy and can't think
        button = self.sender()
        if not button:
            return

        # Translate button position into table viewport coordinates
        pos = button.mapTo(self.roster_table.viewport(), QPoint(0, 0))
        index = self.roster_table.indexAt(pos)

        if index.isValid():
            self.roster_table.removeRow(index.row())

    def _arrange_roster_table(self):
        # orders by team, adjust later for when implementing unknown players

        # get raw rows
        unsorted_rows = []
        for row in range(self.roster_table.rowCount()):
            player = self.roster_table.verticalHeaderItem(row).text()
            team = self.roster_table.cellWidget(row, 0).text()
            rating = self.roster_table.cellWidget(row, 1).text()
            print(team, rating)
            rounds = self.roster_table.item(row, 2).text()
            kpr = self.roster_table.item(row, 3).text()
            wr = self.roster_table.item(row, 4).text()
            pve = self.roster_table.item(row, 5).text()
            unsorted_rows.append([player, team, rating, rounds, kpr, wr, pve])



        sorted_rows = sorted(unsorted_rows, key=lambda x: x[1])
        self.roster_table.setRowCount(0)


        for row in sorted_rows:

            player, team, rating, rounds, kpr, wr, pve = row
            last = self.roster_table.rowCount()
            self.roster_table.insertRow(last)
            self.roster_table.setVerticalHeaderItem(last, QTableWidgetItem(player))
            self.roster_table.setCellWidget(last, 0, QLineEdit())
            if team:
                self.roster_table.cellWidget(last, 0).setText(team)
            self.roster_table.setCellWidget(last, 1, QLineEdit())
            self.roster_table.cellWidget(last, 1).setText(rating)
            self.roster_table.setItem(last, 2, QTableWidgetItem(rounds))
            self.roster_table.setItem(last, 3, QTableWidgetItem(kpr))
            self.roster_table.setItem(last, 4, QTableWidgetItem(wr))
            self.roster_table.setItem(last, 5, QTableWidgetItem(pve))

            delete = QPushButton("Delete")
            delete.clicked.connect(self._delete_from_roster)

            self.roster_table.setCellWidget(last, 6, delete)

    def simulate(self):
        self.simulator_probs.clearContents()
        self.test_round.clearContents()
        self.sim_message.clear()
        self.sim_message.setText("Now running simulations... This may take a while...\n"
                                 "p.s. the app will hang during simulation in this version, sorry :<")
        # n iters
        try:
            n = int(self.n_sims.text())
        except TypeError:
            self.sim_message.setText("Invalid number of simulations.")
            return
        except ValueError:
            self.sim_message.setText("Invalid number of simulations.")
            return

        # pass this off to a worker

        # get values from table
        self.sim_button.setEnabled(False)
        team_dict = self._table_to_numbers()

        self.sim_thread = QThread()
        self.sim_worker = SimulatorWorker(team_dict, iter=n)
        self.sim_thread.started.connect(self.sim_worker.run)
        self.sim_worker.test_round.connect(self._fill_round_table)
        self.sim_worker.agg_stats.connect(self._fill_simulator_probs)
        self.sim_worker.finished.connect(self.simulate_done)

        self.sim_worker.finished.connect(self.sim_thread.quit)
        self.sim_worker.finished.connect(self.sim_worker.deleteLater)
        self.sim_thread.finished.connect(self.sim_thread.deleteLater)
        self.sim_thread.start()


    def _table_to_numbers(self):
        """
        converts table contents to dictionary form {team: (player, info...)}
        :return:
        """
        team_players = defaultdict(dict)
        for row in range(self.roster_table.rowCount()):
            player = self.roster_table.verticalHeaderItem(row).text()
            team = self.roster_table.cellWidget(row, 0).text()
            if not team:
                team = '%%%' # solo marker
            rating_raw = self.roster_table.cellWidget(row, 1).text()
            rating, provisional = (float(rating_raw), 0) if '?' not in rating_raw else (float(rating_raw.split('?')[0]), 1)
            wr = float(self.roster_table.item(row, 4).text().split('%')[0])
            pve = float(self.roster_table.item(row, 5).text().split('%')[0])

            print(player, team, rating, provisional, wr, pve)
            if team != '%%%':
                team_players[team][player] = (team, rating, provisional, wr, pve)
            else:
                team_players[team][player] = (player, rating, provisional, wr, pve)

        pprint(team_players)
        return team_players

    def _fill_round_table(self, feed):
        #
        self.test_round.setRowCount(len(feed))
        for i in range(len(feed)):
            self.test_round.setItem(i, 0, QTableWidgetItem(feed[i][0]))
            self.test_round.setItem(i, 1, QTableWidgetItem(feed[i][1]))
            self.test_round.setItem(i, 2, QTableWidgetItem(feed[i][2]))

    def _fill_simulator_probs(self, agg):

        self.simulator_probs.setRowCount(len(agg))
        players = list(agg.keys())
        for i in range(len(agg)):
            player = players[i]
            stats = agg[player]
            self.simulator_probs.setItem(i, 0, QTableWidgetItem(player))
            self.simulator_probs.setItem(i, 1, QTableWidgetItem(str(stats['team'])))
            self.simulator_probs.setItem(i, 2, QTableWidgetItem(str(stats['avg_kills'])))
            self.simulator_probs.setItem(i, 3, QTableWidgetItem(str(stats['avg_i_placement'])
                                                                + f' ({stats["avg_t_placement"]})'))
            self.simulator_probs.setItem(i, 4, QTableWidgetItem(str(stats['win_count'])
                                                                + f' ({stats["win_pct"]}%)'))
    def simulate_done(self):
        self.sim_message.setText("Simulations complete!")
        self.sim_button.setEnabled(True)

    def simulate_error(self, msg):
        self.sim_message.setText(msg)
        self.sim_button.setEnabled(True)

    # settings and update

    def _make_settings(self):

        blurb_style = """QLabel {
                                        padding: 20;
                                        line-height: normal;
                                      }
                                      QLabel:a {
                                        text-decoration: none;
                                        color: #676767;
                                      }
                                   """

        content = QWidget()
        layout = QVBoxLayout(content)
        title = QLabel("Settings and Update")
        title.setFont(self.title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        # update stuff
        add_round_label = QLabel("""<h2>Round Insertion Tool</h2>""")
        add_round_blurb = QLabel("""<p>
            To add a new round (not a new season), first click on the button "Scan for Rounds" to look for new active rounds.
            You will then be prompted to, for each of the new rounds, copy and paste the link from the Global RR Stats
            Community Document and submit them.  Once you have successfully submitted them, you will be able to update
            the database with the new seasons.</p>
        """)
        add_round_blurb.setWordWrap(True)
        add_round_blurb.setStyleSheet(blurb_style)
        layout.addWidget(add_round_label)
        layout.addWidget(add_round_blurb)

        scan = QWidget()
        scan_layout = QHBoxLayout(scan)
        self.scan_button = QPushButton("Scan for Rounds")
        self.scan_button.setFixedSize(200,30)
        self.scan_button.clicked.connect(self.get_unadded_rounds)
        scan_layout.addWidget(self.scan_button)
        self.scan_msg = QLabel()
        scan_layout.addWidget(self.scan_msg)
        layout.addWidget(scan)


        add_link = QWidget()
        add_link_layout = QHBoxLayout(add_link)

        self.round_choice = QComboBox()
        self.round_choice.setPlaceholderText("Select Round to Add")
        self.round_choice.setStyleSheet(self.opaque)
        add_link_layout.addWidget(self.round_choice)

        self.link_box = QTextEdit()
        self.link_box.setPlaceholderText("Paste the link to the Google Sheet Here")
        self.link_box.setFixedHeight(30)
        add_link_layout.addWidget(self.link_box)

        enter_button = QPushButton("Enter!")
        enter_button.setFixedSize(160, 30)
        enter_button.clicked.connect(self.add_round)
        add_link_layout.addWidget(enter_button)


        layout.addWidget(add_link)

        self.confirmation = QLabel()
        layout.addWidget(self.confirmation)


        update_label = QLabel()
        update_label.setText("""<h2>Scan and Update (Proceed with Caution)</h2>""")
        update_blurb = QLabel("""
            
            <p>Clicking this button will scan the Global Community RR Stats Google Sheet for
            new rounds.  If there are new rounds, then you will be prompted to manually add the new rounds using the
            Round Insertion Tool. <br> 
            
        """)

        update_blurb.setStyleSheet(blurb_style)
        update_blurb.setWordWrap(True)
        layout.addWidget(update_label)
        layout.addWidget(update_blurb)


        self.update_button = QPushButton()
        self.update_button.setText("Update Data")
        self.update_button.setFixedWidth(120)
        self.update_button.clicked.connect(self.update)
        layout.addWidget(self.update_button)

        self.update_status = QLabel()
        layout.addWidget(self.update_status)

        warning = QLabel("""
            <strong>WARNING:</strong> This build does not have an 'Undo' button in case you 
            update after accidentally adding the wrong corresponding link, or if you update while a season's spreadsheet
            is being filled in, resulting in a broken season possibly making it through to the database.  Until a future update
            where this is accounted for, please take into consideration the necessary precautions before updating!  Additionally,
            typos, especially 
            Thank you!""")
        warning.setStyleSheet(blurb_style)
        warning.setWordWrap(True)
        layout.addWidget(warning)



        redact_tool_label = QLabel("<h2>Player Redaction Tool")
        layout.addWidget(redact_tool_label)
        redact_blurb = QLabel("""
            <p>If there is a player you would like to remove from the default view (with the exception of the player lookup),
            you may use this tool to "redact" them.  If you have accidentally redacted the wrong member, 
            you can undo the action with the "Undo" function below it.<br><br>
            <strong>DISCLAIMER:</strong>
            While the developer has tried to find all excommunicated members of
            the community, as an outsider, it is impossible for them to know of every case. In addition to redacting them
            on your own, please also let the developer know through <a href="">this form</a> to help improve future updates
            (when the developer gets around to it).   </p>
        """)
        redact_blurb.setStyleSheet(blurb_style)
        redact_blurb.setWordWrap(True)
        layout.addWidget(redact_blurb)
        redact = QWidget()
        redact_layout = QHBoxLayout(redact)
        self.select_reason = QComboBox()
        self.select_reason.addItems(['Misconduct', 'Cheating', "I don't like them"])
        self.select_reason.setStyleSheet(self.opaque)
        self.redacted_username = QLineEdit()
        self.redacted_username.setPlaceholderText("Please type the username here! (case-sensitive)")
        self.redact_button = QPushButton("Redact")
        self.redact_button.setFixedWidth(120)
        self.redact_button.clicked.connect(self.redact)
        self.redact_label = QLabel()
        redact_layout.addWidget(self.select_reason)
        redact_layout.addWidget(self.redacted_username)
        redact_layout.addWidget(self.redact_button)
        layout.addWidget(redact)
        layout.addWidget(self.redact_label)


        undo_redact_label = QLabel("<h2>Redaction Undo</h2>")
        unredact = QWidget()
        unredact_layout = QHBoxLayout(unredact)
        self.unredacted_username = QLineEdit()
        self.unredacted_username.setPlaceholderText("Please type the username here! (case-sensitive)")
        self.unredact_button = QPushButton("Un-redact")
        self.unredact_button.setFixedWidth(120)
        self.unredact_button.clicked.connect(self.undo_redact)
        self.unredact_label = QLabel()
        unredact_layout.addWidget(self.unredacted_username)
        unredact_layout.addWidget(self.unredact_button)
        layout.addWidget(unredact)
        layout.addWidget(self.unredact_label)

        page_scroll = QScrollArea()
        page_scroll.setWidget(content)
        return page_scroll

    def update(self):
        self.update_status.blockSignals(False)
        self.update_button.setEnabled(False)

        self.thread = QThread()
        self.worker = UpdateWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.error.connect(self.update_error)
        self.worker.finished.connect(self.update_done)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)


        self.update_status.setText("Now Updating... Please don't close the app until the update is complete!")

        self.thread.start()
        self.api.conn.commit()
        self.api = DBOPs("data/stats.db")
        self.fetch = FullAggregation(interface=self.api)

        self.players = self.api.get_players()
        self.rounds = self.api.get_rounds()

    def update_done(self):
        if "Error" not in self.update_status.text():
            self.update_status.setText("Update Complete! (Please restart the app to complete the update!)"
                                       "  If something feels off, please report the issue to plumjuice!")
        self.update_button.setEnabled(True)

    def update_error(self, msg):
        self.update_status.setText(f"Error: {msg}")
        self.get_unadded_rounds()
        self.update_status.blockSignals(True)
        self.update_button.setEnabled(True)

    def get_unadded_rounds(self):
        self.round_choice.clear()
        self.unknowns = []
        for round in self.updater.update_dict:
            if round not in self.updater.rounds.iloc[:, 0].to_list():  # round detected in alive rounds, not in csv
                self.unknowns.append(round)
        self.round_choice.addItems(self.unknowns)
        if self.unknowns:
            self.scan_msg.setText("New rounds detected! (check the dropdown to view them)")
        else:
            self.scan_msg.setText("No new rounds detected! Feel free to continue enjoying the stats!")

    def add_round(self):
        round_name = self.round_choice.currentText()
        link = self.link_box.toPlainText()
        if not link:
            self.confirmation.setText(f"Please enter a link in the text box above!")
            return
        elif not round_name:
            self.confirmation.setText(f"Please select a round from the dropdown above!")
            return
        gid = link.split('=')[-1]
        print(round_name, gid)
        self.updater.add_round(round_name, gid)
        self.confirmation.setText(f"{round_name} Added!")
        self.round_choice.removeItem(self.unknowns.index(round_name))
        self.link_box.clear()

    def redact(self):
        self.redact_label.clear()
        codes = ['X', 'C', 'N']
        idx = self.select_reason.currentIndex()
        player = self.redacted_username.text()
        if player not in self.players:
            self.redact_label.setText("Invalid username! Make sure you have typed the username correctly!")
            return
        else:
            self.api.redact_player(player, codes[idx])
            self.redact_label.setText(f"Successfully redacted {player}!")
            self.redacted_username.clear()
            self.api._save()
            self.api = DBOPs("data/stats.db")

            self.fetch = FullAggregation(interface=self.api)

    def undo_redact(self):
        self.unredact_label.clear()

        player = self.unredacted_username.text()
        if player not in self.players:
            self.unredact_label.setText("Invalid username! Make sure you have typed the username correctly!")
            return
        else:
            self.api.unredact_player(player)
            self.unredact_label.setText(f"Successfully un-redacted {player}!")
            self.unredacted_username.clear()
            self.api._save()
            self.api = DBOPs("data/stats.db")
            self.fetch = FullAggregation(interface=self.api)


    def roll_back(self):
        pass

    # customization
    def _toggle_dark_mode(self):
        dark = """
            QListWidget {
                background-color: #2e3440;
                color: white;
                border: none;
                font: 14px 'Segoe UI';
            }
            QListWidget::item {
                padding: 10px;
            }
            QListWidget::item:selected {
                background-color: #4c566a;
            }
            QListWidget::item:hover {
                background-color: #434c5e;
            }
        """
        light ="""
            QListWidget {
                background-color: #e8e8e8;
                color: black;
                border: none;
                font: 14px 'Segoe UI';
            }
            QListWidget::item {
                padding: 10px;
            }
            QListWidget::item:selected {
                background-color: #8e8e8e;
            }
            QListWidget::item:hover {
                background-color: #bfbfbf;
            }
        """
        dark_gen = """{
            background-color: #232323;
            color: white
        }"""
        light_gen = """{
            background-color: #e8e8e8;
            color: black
        }"""

        dark_bg = """{
            background-color: #121212;
            color: white
        }"""
        light_bg= """{
                    background-color: #d6d6d6;
                    color: black
        }"""

        if self.dark_mode_button.isChecked():
            self.sidebar.setStyleSheet(light)
            self.top_bar.setStyleSheet(f"QWidget {light_gen}")
            self.central.setStyleSheet(f"QWidget {light_bg}")
            self.dark_mode_button.setText("⏾")
            self.dark_mode = self.dark_mode_button.isChecked()
            self.plot_font_color = '#232323'
        else:
            self.sidebar.setStyleSheet(dark)
            self.top_bar.setStyleSheet(f"QWidget {dark_gen}")
            self.central.setStyleSheet(f"QWidget {dark_bg}")
            self.dark_mode_button.setText("☀")
            self.dark_mode = self.dark_mode_button.isChecked()
            self.plot_font_color = '#d6d6d6'
        if hasattr(self, 'selected_data'):
            self.create_stat_graph()
            self.create_rating_dist(self.year)
        # elif hasattr(self, 'lb_dist_data'):
        #     self.lb_scatter.setHtml(self.make_leaderboard_scatter(self.lb_dist_data))



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())
