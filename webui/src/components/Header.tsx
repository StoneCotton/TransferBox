"use client";

import React from "react";
import Button from "./Button";

interface HeaderProps {
  appName: string;
  version: string;
  author: string;
  onShowTutorial?: () => void;
  onShowConfig?: () => void;
}

const Header: React.FC<HeaderProps> = ({
  appName,
  version,
  author,
  onShowTutorial,
  onShowConfig,
}) => {
  return (
    <header className="bg-slate-800 text-white p-4 shadow-md">
      <div className="container mx-auto flex justify-between items-center">
        <div className="flex items-center">
          <h1 className="text-xl font-bold mr-2">{appName}</h1>
          <span className="text-sm bg-slate-700 px-2 py-1 rounded">
            v{version}
          </span>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-sm text-slate-400">by {author}</div>
          <div className="flex items-center space-x-2">
            {onShowConfig && (
              <Button
                label="Config"
                onClick={onShowConfig}
                size="sm"
                variant="primary"
                className="!bg-slate-700 hover:!bg-slate-600 !border-slate-600"
              />
            )}
            {onShowTutorial && (
              <Button
                label="Tutorial"
                onClick={onShowTutorial}
                size="sm"
                variant="primary"
                className="!bg-slate-700 hover:!bg-slate-600 !border-slate-600"
              />
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
