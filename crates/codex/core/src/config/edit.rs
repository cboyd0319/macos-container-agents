use std::path::Path;

use toml_edit::DocumentMut;

#[derive(Debug, Clone)]
pub struct ConfigEdit {
    pub key: String,
    pub value: toml_edit::Value,
}

pub fn tui_pet_edit(pet_id: &str) -> ConfigEdit {
    string_edit("tui.pet", pet_id)
}

pub fn status_line_items_edit(ids: &[String]) -> ConfigEdit {
    ConfigEdit {
        key: "tui.status_line.items".to_string(),
        value: toml_edit::Value::Array(
            ids.iter()
                .map(|id| toml_edit::Value::from(id.as_str()))
                .collect(),
        ),
    }
}

pub fn status_line_use_colors_edit(use_colors: bool) -> ConfigEdit {
    bool_edit("tui.status_line.use_colors", use_colors)
}

pub fn terminal_title_items_edit(ids: &[String]) -> ConfigEdit {
    ConfigEdit {
        key: "tui.terminal_title.items".to_string(),
        value: toml_edit::Value::Array(
            ids.iter()
                .map(|id| toml_edit::Value::from(id.as_str()))
                .collect(),
        ),
    }
}

pub fn syntax_theme_edit(name: &str) -> ConfigEdit {
    string_edit("tui.syntax_theme", name)
}

pub fn keymap_bindings_edit(_context: &str, _action: &str, _bindings: &[String]) -> ConfigEdit {
    ConfigEdit {
        key: "tui.keymap".to_string(),
        value: toml_edit::Value::InlineTable(toml_edit::InlineTable::new()),
    }
}

pub fn keymap_binding_clear_edit(_context: &str, _action: &str) -> ConfigEdit {
    ConfigEdit {
        key: "tui.keymap".to_string(),
        value: toml_edit::Value::InlineTable(toml_edit::InlineTable::new()),
    }
}

fn string_edit(key: &str, value: &str) -> ConfigEdit {
    ConfigEdit {
        key: key.to_string(),
        value: toml_edit::Value::from(value),
    }
}

fn bool_edit(key: &str, value: bool) -> ConfigEdit {
    ConfigEdit {
        key: key.to_string(),
        value: toml_edit::Value::from(value),
    }
}

#[derive(Debug)]
pub struct ConfigEditsBuilder {
    codex_home: std::path::PathBuf,
    edits: Vec<ConfigEdit>,
}

impl ConfigEditsBuilder {
    pub fn new(codex_home: &Path) -> Self {
        Self {
            codex_home: codex_home.to_path_buf(),
            edits: Vec::new(),
        }
    }

    pub fn edit(mut self, edit: ConfigEdit) -> Self {
        self.edits.push(edit);
        self
    }

    pub fn edits(mut self, edits: impl IntoIterator<Item = ConfigEdit>) -> Self {
        self.edits.extend(edits);
        self
    }

    pub async fn apply(self) -> anyhow::Result<()> {
        let path = self.codex_home.join("config.toml");
        let mut document = match tokio::fs::read_to_string(&path).await {
            Ok(source) => source.parse::<DocumentMut>()?,
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => DocumentMut::new(),
            Err(err) => return Err(err.into()),
        };

        for edit in self.edits {
            apply_dotted_value(&mut document, &edit.key, edit.value);
        }

        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        tokio::fs::write(path, document.to_string()).await?;
        Ok(())
    }
}

fn apply_dotted_value(document: &mut DocumentMut, key: &str, value: toml_edit::Value) {
    let mut parts = key.split('.').peekable();
    let mut item = document.as_item_mut();
    while let Some(part) = parts.next() {
        if parts.peek().is_none() {
            item[part] = toml_edit::Item::Value(value);
            return;
        }
        if !item[part].is_table() {
            item[part] = toml_edit::Item::Table(toml_edit::Table::new());
        }
        item = &mut item[part];
    }
}
