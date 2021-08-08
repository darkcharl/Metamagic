#!/usr/bin/env python

import argparse
import re
import logging
import copy
from pprint import pprint

description = """Generates metamagic spell variants from original files"""

class Library(object):
    """
        Library of spells

        Contains spells in a dictionary indexed by the name of the spell.
    """
    def __init__(self, indexed_spells={}):
        self._indexed_spells = indexed_spells
    
    def __repr__(self):
        spells = ', '.join([str(s) for s in self._indexed_spells.values()])
        return f'Library({spells})'

    def add(self, spell):
        self._indexed_spells[spell.name] = spell

    """ Extend library with metamagic spells """
    def extend(self, d, copy_orig=False):
        md = {}
        if copy_orig:
            md = copy.deepcopy(d)
        for spellname, spelldata in d.items():
            usecost = ""
            spellflags = ""
            if 'UseCosts' in spelldata['data']:
                usecost = spelldata['data']['UseCosts']
            if 'SpellFlags' in spelldata['data']:
                spellflags = spelldata['data']['SpellFlags']
            
            """ Skip containers """
            if spellflags.find("IsLinkedSpellContainer") > -1:
                logging.debug(f"Skipping {spellname} as it is a container")
                continue

            container_spells = []
            """ Original spell, containerized version """
            container_spells.append(add_original(md, spellname, spelldata))

            """ Quicken """
            if usecost.find("SpellSlot") > -1 and usecost.find("BonusAction") == -1:
                logging.debug(f"Adding spell {spellname}")
                container_spells.append(add_spell(md, spellname, spelldata))
            
            """ Subtle """
            #if spellflags.find("HasVerbalComponent") > -1:
            #    logging.debug(f"Adding subtle {spellname}")
            #    container_spells.append(add_subtle(md, spellname, spelldata))

            """ Container """
            if len(container_spells) > 1:
                logging.debug(f"Creating container for {spellname} using {container_spells}")
                add_container(md, spellname, spelldata, container_spells)
        return md

    def get_spellname(self, line):
        re_name = r'(?P<headertype>new entry) "(?P<value>.+)"'
        m = re.match(re_name, line)
        if not m:
            return ""
        return m.group('value')

    def get_entrytype(self, line):
        re_type = r'(?P<headertype>type) "(?P<value>.+)"'
        m = re.match(re_type, line)
        if not m:
            return ""
        return m.group('value')

    def get_spellparent(self, line):
        re_parent = r'(?P<headertype>using) "(?P<value>.+)"'
        m = re.match(re_parent, line)
        if not m:
            return ""
        return m.group('value')

    def get_spelldata(self, line):
        re_data = r'(?P<datatype>data) "(?P<key>.+)" "(?P<value>.*)"'
        m = re.match(re_data, line)
        if not m:
            return {}
        k = m.group('key')
        v = m.group('value')
        return {k:v}

    def load(self, filename):
        with open(filename, 'r') as src:
            self._data = src.read()
        self.load_spells()
        del self._data
    
    def load_spells(self):
        """ Reads spell block definitions in file into a Library of Spells """
        
        """ Break up data into blocks that are separated by empty lines in the file """
        for block in self._data.split('\n\n'):
            """ Break up the block into lines for further processing """
            lines = block.split('\n')
            
            """ Skip empty lines """
            if not lines:
                continue

            """ We first need to process headers """

            """ Spell name is stored in 'new entry' """
            spellname = self.get_spellname(lines.pop(0))
            if not spellname:
                logging.warning("spell name not found, skipping block")
                continue

            """ The entry type for spells is stored via 'type' and is always be set to 'SpellData' """
            entrytype = self.get_entrytype(lines.pop(0))
            if entrytype != "SpellData":
                logging.warning("entry type not SpellData")
                continue

            """ The actual spell type (e.g. 'Projectile') is stored simply as 'data' """
            spelltype = self.get_spelldata(lines.pop(0))
            if not spelltype:
                logging.warning("spell type not found, skipping block")
                continue

            """ 
                Settings might be inherited from another spell pointed to via the 'using' key
                This is an optional setting though so we only pop() this line if exists.
            """
            peekline = lines[0]
            spellparent = self.get_spellparent(peekline)
            if spellparent:
                lines.pop(0)

            """ The rest of the lines should all be in 'data' """
            spelldata = {}
            for line in lines[1:]:
                d = self.get_spelldata(line)
                if d:
                    spelldata.update(d)

            """ We need to put back the spell type from the header into 'data' """
            spelldata.update(spelltype)

            """ Create our shiny new spell object """
            spell = Spell(spellname, spellparent, spelldata)

            """ Add compiled spell """
            self.add(spell)

    def load(self, filename):
        with open(filename, 'r') as src:
            self._data = src.read()
        self.load_spells()
        del self._data

    def print(self):
        for spellname, spell in self._indexed_spells.items():
            print(f'{spell.name}')
            if spell.parent:
                print(f'  Parent: {spell.parent}')
            for k, v in spell.data.items():
                print(f'  {k}: {v}')
            print()


class Spell(object):
    """
        Spell Object
    """    
    def __init__(self, name, parent="", data={}):
        """Initializes a Spell object

        Args:
            name (str):   Name of the spell. 
            type (str):   Type of the spell.
            parent (str): Name of the spell settings are inherited from.
            data (dict):  Dictionary of spell settings.
        """        
        self._name = name
        self._parent = parent
        self._data = data

    def __repr__(self):
        return f'Spell({self._name})'

    @property
    def name(self):
        """This is the name of the Spell

        Returns:
            str: Spell name
        """        
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @name.deleter
    def name(self):
        del self._name

    @property
    def parent(self):
        """Spell inherits settings from this parent Spell

        Returns:
            str: Parent spell name (e.g. "Projectile_MagicMissile")
        """        
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    @parent.deleter
    def parent(self):
        del self._parent

    @property
    def data(self):
        """Dictionary with Spell settings

        Returns:
            dict: Spell settings in key/value format
        """        
        return self._data

    @data.setter
    def data(self, value):
        self._data = value

    @data.deleter
    def data(self):
        del self._data





def create_spell(spellname, spelldata, customdata=None, postfix='Clone', container_postfix='Metamagic'):
    """Clones and modifies a spell with custom data

    Args:
        spellname (str): name of the original spell
        spelldata (dict): dictionary of data of the original spell
        customdata (dict, optional): Customized data in spelldata dictionary format. Defaults to None.
        postfix (str, optional): Appends this to the original spell name to create new spell name. Defaults to 'Clone'. 
        container_postfix (str, optional): Postfix used in naming the container for all these spells. Defaults to 'Metamagic'.

    Using the defaults Target_MageArmor will yield Target_MageArmor_Clone that will be placed in a container Target_MageArmor_Metamagic.

    Returns:
        string, dict: spell name and a spell object in the format {'spellname_str':'spelldata_dict'}
    """    
    name = f"{spellname}_{postfix}"
    spell = {}
    d = copy.deepcopy(spelldata)
    d['data']['SpellContainerID'] = f'{spellname}_{container_postfix}'
    #if customdata:
    #    d.update(customdata)
    spell[name] = d
    return name, spell

""" Implements original version of spell modifying only the container """
def add_original(library, spellname, spelldata, postfix='Original'):
    name, spell = create_spell(spellname, spelldata, None, postfix)
    library.update(spell)
    return name


""" Adds spell version to spell list (Action => BonusAction) """
def add_spell(library, spellname, spelldata, postfix='spell'):
    customdata = {}
    usecost = re.sub('ActionPoint(Group)?', 'BonusActionPoint', spelldata['data']['UseCosts'])
    customdata = {
        'data': {
            'UseCosts' : f'{usecost}',
            'RootSpellID' : f'{spellname}'
        }
    }
    name, spell = create_spell(spellname, spelldata, customdata, postfix)
    library.update(spell)
    return name


""" Adds subtle version to spell list (no verbal component required) """
def add_subtle(md, spellname, spelldata):
    subtle_name = f"{spellname}_Subtle"
    subtle_data = copy.deepcopy(spelldata)
    spellflags = subtle_data['data']['SpellFlags']
    spellflags_items = spellflags.split(';')
    spellflags_filtered = [sf for sf in spellflags_items if sf != "HasVerbalComponent"]
    subtle_data['data']['SpellFlags'] = ';'.join(spellflags_filtered)
    subtle_data['data']['SpellContainerID'] = f'{spellname}_Metamagic'
    md[subtle_name] = subtle_data
    return subtle_name


""" Adds container for created metaspells """
def add_container(md, spellname, spelldata, container_spells):
    container_name = f"{spellname}_Metamagic"
    if not "DisplayName" in spelldata['data']:
        return
    if not "SpellFlags" in spelldata['data']:
        return
    displayname = spelldata['data']['DisplayName']
    spellflags = spelldata['data']['SpellFlags'].split(';')
    spellflags.append('IsLinkedSpellContainer')
    
    container_data = {
        'data' : {
            'DisplayName'     : f"{displayname} (Metamagic)",
            'SpellFlags'      : f"{';'.join(spellflags)}",
            'ContainerSpells' : f"{';'.join(container_spells)}"
        },
        'type' : "SpellData",
        'using': f"{spellname}"
    }
    md[container_name] = container_data


""" Adds meta versions of spells """
def add_meta_versions(d, copy_orig=False):
    md = {}
    if copy_orig:
        md = copy.deepcopy(d)
    for spellname, spelldata in d.items():
        usecost = ""
        spellflags = ""
        if 'UseCosts' in spelldata['data']:
            usecost = spelldata['data']['UseCosts']
        if 'SpellFlags' in spelldata['data']:
            spellflags = spelldata['data']['SpellFlags']
        
        """ Skip containers """
        if spellflags.find("IsLinkedSpellContainer") > -1:
            logging.debug(f"Skipping {spellname} as it is a container")
            continue

        container_spells = []
        """ Original spell, containerized version """
        container_spells.append(add_original(md, spellname, spelldata))

        """ Quicken """
        if usecost.find("SpellSlot") > -1 and usecost.find("BonusAction") == -1:
            logging.debug(f"Adding spell {spellname}")
            container_spells.append(add_spell(md, spellname, spelldata))
        
        """ Subtle """
        #if spellflags.find("HasVerbalComponent") > -1:
        #    logging.debug(f"Adding subtle {spellname}")
        #    container_spells.append(add_subtle(md, spellname, spelldata))

        """ Container """
        if len(container_spells) > 1:
            logging.debug(f"Creating container for {spellname} using {container_spells}")
            add_container(md, spellname, spelldata, container_spells)
    return md


""" Recreates library using spell definitions """
def recreate_library(d):
    lines = []
    for spellname, spelldata in d.items():
        """ Fixed order header """
        lines.append(f'new entry "{spellname}"')
        spellspec = spelldata.pop('type', None)
        lines.append(f'type "{spellspec}"')
        spelltype = spelldata['data'].pop('SpellType', None)
        lines.append(f'data "SpellType" "{spelltype}"')
        using = spelldata.pop('using', None)
        if using:
            lines.append(f'using "{using}"')
        for meta, values in spelldata.items():
            if meta == "data":
                for k, v in values.items():
                    lines.append(f'{meta} "{k}" "{v}"')
            else:
                lines.append(f'{meta} "{values}"')
        lines.append('')
    return '\n'.join(lines)
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('source', help='source spell definitions file')
    parser.add_argument('--verbose', '-v', action='count', default=0, 
                        help='increase verbosity')
    args = vars(parser.parse_args())

    """ File settings """
    source = args['source']
    destination = f"{'.'.join(source.split('.')[:-1])}_Metamagic.txt"

    """ Loglevel settings """
    if args['verbose']:
        logging.basicConfig(format='%(levelname)s %(message)s', 
                            encoding='utf-8', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(levelname)s %(message)s', 
                            encoding='utf-8', level=logging.WARN)

    """ Debug """
    logging.debug(f"Source: {source}, Destination: {destination}")

    """ Create and load Spell Library """
    library_orig = Library()
    library_orig.load(source)
    
    """ Debug """
    if args['verbose'] > 0:
        library_orig.print()

    #extended_spell_list = add_meta_versions(original_spell_list)

    #if args['verbose'] > 0:
    #    pprint(extended_spell_list)

    #with open(destination, 'w') as dst:
    #    dst.write(recreate_library(extended_spell_list))
