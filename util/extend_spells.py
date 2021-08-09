#!/usr/bin/env python

import argparse
import re
import logging
import copy
from pprint import pprint

description = """Generates Metamagic Spells from original"""

class Library(object):
    """
        Library of spells

        Contains spells in a dictionary indexed by the name of the spell.
    """
    def __init__(self):
        self._indexed_spells = {}
        self._grouped_spells = {}
    
    def __repr__(self):
        spells = ', '.join([str(s) for s in self._indexed_spells.values()])
        return f'Library({spells})'

    @property
    def indexed_spells(self):
        return self._indexed_spells

    def add(self, spell):
        self._indexed_spells[spell.name] = spell

    def find_spellgroups(self):
        for spellname, spell in self._indexed_spells.items():
            spellgroup = spell.get_spellgroup()
            if spellgroup not in self._grouped_spells:
                self._grouped_spells[spellgroup] = []
            self._grouped_spells[spellgroup].append(spell)

    def print_spellgroups(self):
        for spellgroup, spells in self._grouped_spells.items():
            spelllist = ','.join([s.name for s in spells])
            print(f'{spellgroup}: {spelllist}')

    """ Extend library with metamagic spells """
    def create_metamagic(self):
        metamagic_library = Library()

        for spellgroup, spells in self._grouped_spells.items():
            logging.debug(f"Creating meta spells for {spellgroup} with spells {spells}")
            container = Container(spells[0])
            container.name = f'{spellgroup}_Metamagic'
            meta_spells = []
            for spell in spells:
                spell_containerized = spell.containerized(container)
                spell_quickened = spell.quickened(container)
                spell_subtle = spell.subtle(container)

                """ Add containerized spell to meta spells """
                meta_spells.append(spell_containerized)

                """ Only add quickened variant for Spells that consume SpellSlots and don't already use BonusAction """
                if spell.uses_spellslot() and not spell.uses_bonusaction():
                    meta_spells.append(spell_quickened)

                """ Only add subtle variant for Spells that consume SpellSlots and require verbal component """
                if spell.uses_spellslot() and spell.has_verbalcomponent():
                    meta_spells.append(spell_subtle)

            """ Add spells and container to Library only if Container holds more than just the containerized original Spell """
            if meta_spells:
                for s in meta_spells:         
                    container.add(s)

                metamagic_library.add(container)
                for s in meta_spells:
                    metamagic_library.add(s)

        return metamagic_library

    def load_spells(self):
        """ Processes spell block definitions into Spells """
        
        """ Break up data into blocks that are separated by empty lines in the file """
        for block in self._data.split('\n\n'):
            """ Break up the block into lines for further processing """
            lines = block.split('\n')
            
            """ Skip empty lines """
            if len(lines) < 3:
                logging.warning("short block found")
                continue

            spell = Spell()
            spell.load(lines)

            """ Add compiled spell """
            self.add(spell)

    def load(self, filename):
        """ Loads spells into Library from file """
        with open(filename, 'r') as src:
            self._data = src.read()
        self.load_spells()
        self.find_spellgroups()
        del self._data

    def print(self):
        """ Human readable representation of the Library and Spells """
        for spellname, spell in self._indexed_spells.items():
            print(f'{spell.name}')
            if spell.parent:
                print(f'  Parent: {spell.parent}')
            for k, v in spell.data.items():
                print(f'  {k}: {v}')
            print()
    
    def print_entries(self):
        """ Prints library in file format """
        print(self.to_entries())
    
    def save(self, filename):
        """ Saves library properly formatted to file """
        with open(filename, 'w') as dst:
            dst.write(self.to_entries())

    def to_entries(self):
        """ Recreates library in file format """
        entries = []
        for spellname, spell in self._indexed_spells.items():
            entries.append(spell.to_entry())
        return('\n\n'.join(entries))



class Spell(object):
    """ Spell Object """    
    def __init__(self):
        self._name = ""
        self._entrytype = 'SpellData'
        self._parent = ""
        self._data = {}

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @name.deleter
    def name(self):
        del self._name

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    @parent.deleter
    def parent(self):
        del self._parent

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value

    @data.deleter
    def data(self):
        del self._data

    def __repr__(self):
        return f'Spell({self._name})'

    def clone(self):
        new = Spell()
        new._name = copy.deepcopy(self._name)
        new._entrytype = copy.deepcopy(self._entrytype)
        new._type = copy.deepcopy(self._type)
        new._parent = copy.deepcopy(self._parent)
        new._data = copy.deepcopy(self._data)
        return new
    
    def alter(self, spelldata):
        self._data.update(spelldata)

    def quickened(self, container):
        spell_quickened = self.clone().containerized(container)
        spell_quickened.name = f'{self._name}_Quickened'
        spell_quickened.add_spelldata('DisplayName', 'Cast Quickened')
        spell_quickened.replace_spelldata('UseCosts', 'ActionPoint(Group)?', 'BonusAction')
        return spell_quickened

    def subtle(self, container):
        spell_subtle = self.clone().containerized(container)
        spell_subtle.name = f'{self.name}_Subtle'
        spell_subtle.add_spelldata('DisplayName', 'Cast Subtle')
        spell_subtle.replace_spelldata('SpellFlags', 'HasVerbalComponent[;]*', '')
        return spell_subtle

    def containerized(self, container):
        spell_containerized = self.clone()
        spell_containerized.name = f'{self.name}_Original'
        spell_containerized.add_spelldata('DisplayName', 'Cast Unmodified')
        spell_containerized.add_spelldata('SpellContainerID', f'{container.name}')
        spell_containerized.add_spelldata('RootSpellID', f'{container.name}')
        if self.is_container:
            spell_containerized.replace_spelldata('SpellFlags', r';IsLinkedSpellContainer', r'')
        return spell_containerized
    
    def add_spelldata(self, key, value):
        self._data[key] = value

    def find_spelldata(self, key, find_re):
        if self._data.get(key, None) and re.search(find_re, self._data[key]):
            return True
        return False
    
    def get_spelldata(self, key):
        return self._data.get(key, None)

    def replace_spelldata(self, key, find_re, replace_re):
        if self.find_spelldata(key, find_re):
            self._data[key] = re.sub(find_re, replace_re, self._data[key])

    def get_spellgroup(self):
        if self.has_containerspell():
            return self.get_spelldata('SpellContainerID')
        elif self.has_rootspell():
            return self.get_spelldata('RootSpellID')
        return self._name

    def is_container(self):
        return self.find_spelldata('SpellFlags', 'IsLinkedSpellContainer')

    def has_powerlevel(self):
        return self.find_spelldata('PowerLevel', '[0-9]+')

    def has_containerspell(self):
        return self.get_spelldata('SpellContainerID')

    def has_rootspell(self):
        return self.get_spelldata('RootSpellID')

    def has_verbalcomponent(self):
        return self.find_spelldata('SpellFlags', 'HasVerbalComponent')

    def uses_bonusaction(self):
        return self.find_spelldata('UseCosts', 'BonusAction')
        
    def uses_spellslot(self):
        return self.find_spelldata('UseCosts', 'SpellSlot')

    def parse_spellname(self, line):
        re_name = r'(?P<headertype>new entry) "(?P<value>.+)"'
        m = re.match(re_name, line)
        if not m:
            return ""
        return m.group('value')

    def parse_entrytype(self, line):
        re_type = r'(?P<headertype>type) "(?P<value>.+)"'
        m = re.match(re_type, line)
        if not m:
            return ""
        return m.group('value')

    def parse_spellparent(self, line):
        re_parent = r'(?P<headertype>using) "(?P<value>.+)"'
        m = re.match(re_parent, line)
        if not m:
            return ""
        return m.group('value')

    def parse_spelldata(self, line):
        re_data = r'(?P<datatype>data) "(?P<key>.+)" "(?P<value>.*)"'
        m = re.match(re_data, line)
        if not m:
            return {}
        k = m.group('key')
        v = m.group('value')
        return {k:v}

    def load(self, lines):
        """ Processes a block of lines into a Spell """

        """ Spell name is stored in 'new entry' """
        self._name = self.parse_spellname(lines.pop(0))
        
        """ The entry type for spells is stored via 'type' and is always be set to 'SpellData' """
        self._entrytype = self.parse_entrytype(lines.pop(0))
        
        """ The actual spell type (e.g. 'Projectile') is stored simply as 'data' """
        self._type = self.parse_spelldata(lines.pop(0))
        
        """ 
            Settings might be inherited from another spell pointed to via the 'using' key
            This is an optional setting though so we only pop() this line if exists.
        """
        peekline = lines[0]
        self._parent = self.parse_spellparent(peekline)
        if self._parent:
            lines.pop(0)

        """ The rest of the lines should all be in 'data' """
        for line in lines:
            d = self.parse_spelldata(line)
            if d:
                self._data.update(d)

        """ We need to put back the spell type from the header into 'data' """
        self._data.update(self._type)

    def to_entry(self):
        """ Implements storage format used in files """

        """ Header first """
        lines = [
            f'''new entry "{self._name}"''',
            f'''type "{self._entrytype}"''',
            f'''data "SpellType" "{self._data['SpellType']}"''',
            f'''using "{self._parent}"'''
        ]
    
        """ Remove parent line if not applicable """
        if not self._parent:
            lines.pop()

        """ Already specified in above header """
        del self._data['SpellType']

        """ Write remaining data entries """
        for k, v in self._data.items():
            lines.append(f'data "{k}" "{v}"')

        return '\n'.join(lines) 


class Container(Spell):
    """ Containers are special spells that contain other spells through "ContainerSpells" """    
    def __init__(self, spell):
        super().__init__()
        self._name = copy.deepcopy(spell._name)
        self._entrytype = copy.deepcopy(spell._entrytype)
        self._type = copy.deepcopy(spell._type)
        self._children = []
        self._data = copy.deepcopy(spell._data)
        
        self.add_spelldata('ContainerSpells', '')
        if not self.is_container():
            self.replace_spelldata('SpellFlags', r'^(.*)$', r'\1;IsLinkedSpellContainer')
    
    def __repr__(self):
        return f'Container({self._name})'
    
    def add(self, spell):
        self._children.append(spell)
        children = ";".join([s.name for s in self._children])
        self.add_spelldata('ContainerSpells', children)

    @property
    def children(self):
        return self._children

    @children.setter
    def children(self, value):
        self._children = value

    @children.deleter
    def children(self):
        del self._children

    def add_child(self, spell):
        self._children.append(spell)


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
    library = Library()
    library.load(source)
    
    """ Debug """
    if args['verbose'] > 0:
        library.print()

    """ Extend Library with metamagic version of Spells """
    metamagic_library = library.create_metamagic()

    """ Debug """
    if args['verbose'] > 0:
        metamagic_library.print()

    metamagic_library.save(destination)


