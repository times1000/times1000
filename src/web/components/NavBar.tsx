import React from 'react';
import { Link } from 'react-router-dom';

const NavBar: React.FC = () => {
  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">
          <span className="logo-text">*1000</span>
        </Link>
        
        <ul className="nav-menu">
          <li className="nav-item">
            <Link to="/" className="nav-link">
              Dashboard
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/agents/new" className="nav-link">
              New Agent
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/logs" className="nav-link">
              API Logs
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default NavBar;